from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
import json

logger = logging.getLogger(__name__)


class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> str:
        """Получение/обновление токена доступа"""
        token_lifetime = 86390  # 24 * 60 * 60 - 10 seconds
        current_time = datetime.now()

        # Проверяем, есть ли у пользователя токен и не истек ли он
        if (user.bothub_access_token and user.bothub_access_token_created_at and
                (current_time - user.bothub_access_token_created_at).total_seconds() < token_lifetime):
            return user.bothub_access_token

        # Получаем новый токен
        logger.info(f"Получаю новый токен доступа для пользователя {user.id}")
        response = await self.client.authorize(
            user.tg_id,
            user.first_name or user.username or "Telegram User",
            user.bothub_id,
            user.referral_code
        )

        # Обновляем данные пользователя
        user.bothub_access_token = response["accessToken"]
        user.bothub_access_token_created_at = current_time

        if not user.bothub_id:
            user.bothub_id = response["user"]["id"]

            if "groups" in response["user"] and response["user"]["groups"]:
                user.bothub_group_id = response["user"]["groups"][0]["id"]

                if "chats" in response["user"]["groups"][0] and response["user"]["groups"][0]["chats"]:
                    chat_data = response["user"]["groups"][0]["chats"][0]
                    chat = Chat(
                        id=0,
                        user_id=user.id,
                        chat_index=user.current_chat_index,
                        bothub_chat_id=chat_data["id"],
                        name=chat_data.get("name")
                    )

                    if "settings" in chat_data and "model" in chat_data["settings"]:
                        chat.bothub_chat_model = chat_data["settings"]["model"]

        # Устанавливаем модели по умолчанию если их нет
        if not user.gpt_model and hasattr(self, '_is_gpt_model'):
            if self._is_gpt_model(chat.bothub_chat_model if 'chat' in locals() else None):
                user.gpt_model = chat.bothub_chat_model

        if not user.image_generation_model:
            user.image_generation_model = "dall-e"

        return user.bothub_access_token

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """Создание нового чата по аналогии с PHP версией"""
        name = f'Chat {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        access_token = await self.get_access_token(user)

        # Если нет группы, создаем новую
        if not user.bothub_group_id:
            logger.info(f"Создание новой группы для пользователя {user.id}")
            group_response = await self.client.create_new_group(access_token, "Telegram")
            user.bothub_group_id = group_response["id"]

        try:
            if is_image_generation:
                # Логика для создания чата генерации изображений
                logger.info(f"Создание чата для генерации изображений")

                # Получаем модель для генерации изображений
                image_model = user.image_generation_model

                # Специальная логика для flux моделей (как в PHP)
                if 'flux' in image_model:
                    # Получаем список доступных моделей
                    models = await self.client.list_models(access_token)
                    
                    # Логируем доступные модели для отладки
                    logger.info(f"🔍 Доступные модели: {json.dumps([{
                        'id': m.get('id'),
                        'name': m.get('name'),
                        'is_allowed': m.get('is_allowed') or m.get('isAllowed'),
                        'features': m.get('features', []),
                        'parent_id': m.get('parent_id')
                    } for m in models], ensure_ascii=False, indent=2)}")
                    
                    # Ищем родительскую модель для Flux
                    parent_model = None
                    for model in models:
                        logger.info(f"🔍 Проверяем модель: id={model.get('id')}, name={model.get('name')}, "
                                  f"parent_id={model.get('parent_id')}")
                        # Проверяем различные варианты идентификации Flux модели
                        is_flux = any([
                            model.get("id") == "replicate-flux",
                            model.get("name", "").lower() == "flux",
                            "flux" in model.get("id", "").lower(),
                            "flux" in model.get("name", "").lower(),
                            model.get("parent_id") == "replicate-flux"
                        ])
                        if is_flux and (model.get("is_allowed") or model.get("isAllowed")):
                            parent_model = model
                            logger.info(f"✅ Найдена подходящая Flux модель: {json.dumps(model, ensure_ascii=False, indent=2)}")
                            break

                    if not parent_model:
                        raise Exception("Модель Flux недоступна на сервере")
                    
                    # Используем ID самой модели для создания чата
                    model_id_for_chat = parent_model.get("id")  # Убираем parent_id
                    logger.info(f"📝 Создаем чат с model_id: {model_id_for_chat}")
                    
                    response = await self.client.create_new_chat(
                        access_token, user.bothub_group_id, name, model_id_for_chat
                    )
                    chat_id = response['id']
                    # Больше не нужно обновлять родительскую модель, так как мы используем правильный ID
                    model_id = model_id_for_chat
                else:
                    response = await self.client.create_new_chat(
                        access_token, user.bothub_group_id, name, image_model
                    )
                    chat_id = response['id']
                    model_id = response.get('model_id', image_model)

                # Обновляем данные чата
                chat.bothub_chat_id = chat_id
                chat.bothub_chat_model = model_id

            else:
                # Логика для создания текстового чата
                logger.info(f"Создание текстового чата")

                # Получаем модель по умолчанию
                default_model = await self._get_default_model(user)

                # Создаем чат с родительской моделью
                response = await self.client.create_new_chat(
                    access_token, user.bothub_group_id, name, default_model.get('parent_id')
                )

                chat_id = response['id']
                model_id = default_model['id']

                # Обновляем данные чата
                chat.bothub_chat_id = chat_id
                if not chat.bothub_chat_model:
                    chat.bothub_chat_model = model_id

                # Проверяем, нужно ли сохранить настройки чата
                should_save_settings = (
                        (chat.bothub_chat_model and chat.bothub_chat_model != model_id) or
                        not chat.context_remember or
                        chat.system_prompt
                )

                if should_save_settings:
                    # Определяем максимальное количество токенов
                    max_tokens = None
                    if chat.bothub_chat_model:
                        # В полной версии здесь будет получение информации о модели
                        pass

                    # Сохраняем настройки чата
                    await self.client.save_chat_settings(
                        access_token,
                        chat_id,
                        chat.bothub_chat_model or model_id,
                        max_tokens,
                        chat.context_remember,
                        chat.system_prompt
                    )
                    logger.info(f"Сохранены настройки для чата {chat_id}")

        except Exception as e:
            logger.error(f"Ошибка при создании чата: {str(e)}")

            # Если группа не найдена или возникла ошибка 500, создаем новую и пробуем снова
            if "404" in str(e) or "500" in str(e):
                group_response = await self.client.create_new_group(access_token, "Telegram")
                user.bothub_group_id = group_response["id"]
                # Рекурсивно создаем чат с новой группой (но только один раз)
                await self.create_new_chat(user, chat, is_image_generation)
            else:
                raise Exception(f"Не удалось создать чат: {str(e)}")

    async def _get_default_model(self, user: User) -> Dict[str, Any]:
        """Получение модели по умолчанию (аналог PHP)"""
        access_token = await self.get_access_token(user)
        models = await self.client.list_models(access_token)

        # Фильтруем модели по критериям
        for model in models:
            if ((model.get("is_default") or model.get("isDefault")) and
                    (model.get("is_allowed") or model.get("isAllowed")) and
                    "TEXT_TO_TEXT" in model.get("features", [])):
                return model

        # Если не найдена модель по умолчанию, берем первую доступную
        for model in models:
            if ((model.get("is_allowed") or model.get("isAllowed")) and
                    "TEXT_TO_TEXT" in model.get("features", [])):
                return model

        # Если ничего не найдено, возвращаем первую модель или пустой словарь
        return models[0] if models else {}

    async def send_message(self, user: User, chat: Chat, message: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """Отправка сообщения"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)

        try:
            result = await self.client.send_message(
                access_token,
                chat.bothub_chat_id,
                message,
                files
            )
            return result
        except Exception as e:
            # Если чат не найден, создаем новый и пробуем снова
            if "CHAT_NOT_FOUND" in str(e):
                logger.warning(f"Чат не найден, создаю новый для пользователя {user.id}")
                await self.create_new_chat(user, chat)
                return await self.client.send_message(
                    access_token,
                    chat.bothub_chat_id,
                    message,
                    files
                )
            raise

    async def reset_context(self, user: User, chat: Chat) -> None:
        """Сброс контекста чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.reset_context(access_token, chat.bothub_chat_id)

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """Получение статуса веб-поиска для чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

    async def enable_web_search(self, user: User, chat: Chat, enabled: bool) -> None:
        """Включение/выключение веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, enabled)

    async def save_system_prompt(self, user: User, chat: Chat) -> None:
        """Сохранение системного промпта"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.save_system_prompt(access_token, chat.bothub_chat_id, chat.system_prompt)

    async def generate_telegram_connection_link(self, user: User, settings) -> str:
        """Генерация ссылки для подключения Telegram к аккаунту"""
        access_token = await self.get_access_token(user)
        response = await self.client.generate_telegram_connection_token(access_token)

        # Из ответа получаем токен
        if "telegramConnectionToken" in response:
            token = response["telegramConnectionToken"]
        elif "data" in response and "telegramConnectionToken" in response["data"]:
            token = response["data"]["telegramConnectionToken"]
        else:
            token = ""

        # Пробуем извлечь ID из токена JWT
        if token:
            try:
                # Разбиваем JWT токен на части
                parts = token.split('.')
                if len(parts) >= 2:
                    # Декодируем тело токена (вторая часть)
                    import base64
                    import json

                    # Правильное декодирование base64
                    padding = '=' * (4 - len(parts[1]) % 4)
                    decoded = base64.b64decode(parts[1] + padding)
                    payload = json.loads(decoded)

                    # Извлекаем ID из токена
                    if "id" in payload:
                        bothub_id = payload["id"]
                        logger.info(f"Извлечен bothub_id из токена: {bothub_id}")
                        # Обновляем bothub_id пользователя
                        user.bothub_id = bothub_id
            except Exception as e:
                logger.error(f"Ошибка при извлечении ID из токена: {e}")

        web_url = settings.BOTHUB_WEB_URL
        return f"{web_url}?telegram-connection-token={token}"

    async def transcribe_voice(self, user: User, chat: Chat, file_path: str) -> str:
        """Транскрибирование голосового сообщения"""
        access_token = await self.get_access_token(user)
        return await self.client.whisper(access_token, file_path)