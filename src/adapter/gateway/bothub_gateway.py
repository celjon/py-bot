# src/adapter/gateway/bothub_gateway.py

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat

logger = logging.getLogger(__name__)


class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> str:
        """
        Получение/обновление токена доступа

        Args:
            user: Пользователь

        Returns:
            str: Токен доступа
        """
        token_lifetime = 86390  # 24 * 60 * 60 - 10 seconds
        current_time = datetime.now()

        # Проверяем, есть ли у пользователя токен и не истек ли он
        if (user.bothub_access_token and user.bothub_access_token_created_at and
                (current_time - user.bothub_access_token_created_at).total_seconds() < token_lifetime):
            logger.debug(f"Использую существующий токен для пользователя {user.id}")
            return user.bothub_access_token

        # Получаем новый токен
        logger.info(f"Получаю новый токен доступа для пользователя {user.id}")
        response = await self.client.authorize(
            user.telegram_id,
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

        return user.bothub_access_token

    async def get_default_model(self, user: User) -> Dict[str, Any]:
        """
        Получение модели по умолчанию

        Args:
            user: Пользователь

        Returns:
            Dict[str, Any]: Модель по умолчанию
        """
        access_token = await self.get_access_token(user)
        models = await self.client.list_models(access_token)

        # Ищем модель по умолчанию для текстовых чатов
        for model in models:
            if model.get("is_default", False) and "TEXT_TO_TEXT" in model.get("features", []):
                return model

        # Если не нашли, ищем первую доступную
        for model in models:
            if "TEXT_TO_TEXT" in model.get("features", []) and model.get("is_allowed", False):
                return model

        # Если вообще не нашли моделей, возвращаем пустую модель
        return {"id": None, "parent_id": None}

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """
        Создание нового чата

        Args:
            user: Пользователь
            chat: Чат
            is_image_generation: Флаг создания чата для генерации изображений
        """
        logger.info(f"Создание нового чата для пользователя {user.id}")
        access_token = await self.get_access_token(user)

        # Если нет группы, создаем новую
        if not user.bothub_group_id:
            logger.info(f"Создание новой группы для пользователя {user.id}")
            group_response = await self.client.create_new_group(access_token, "Telegram")
            user.bothub_group_id = group_response["id"]

        try:
            # Выбор модели в зависимости от типа чата
            if is_image_generation:
                # Для генерации изображений используем модель из настроек пользователя
                # или dalle по умолчанию
                model_id = user.image_generation_model or "dall-e"
                parent_model = model_id
                chat_name = f"Telegram Image Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                # Для текстового чата получаем модель по умолчанию
                default_model = await self.get_default_model(user)
                model_id = default_model.get("id")
                parent_model = default_model.get("parent_id") or model_id
                chat_name = f"Telegram Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Создаем чат с родительской моделью
            response = await self.client.create_new_chat(
                access_token,
                user.bothub_group_id,
                chat_name,
                parent_model
            )

            chat.bothub_chat_id = response["id"]
            chat.bothub_chat_model = model_id

            # Если это не чат для генерации изображений и у нас есть конкретная модель,
            # сохраняем настройки чата с этой моделью
            if not is_image_generation and model_id:
                max_tokens = None
                if model_id and "gpt-" in model_id:
                    max_tokens = 4000

                await self.client.save_chat_settings(
                    access_token,
                    chat.bothub_chat_id,
                    model_id,
                    max_tokens,
                    chat.context_remember,
                    chat.system_prompt
                )

        except Exception as e:
            logger.error(f"Ошибка при создании чата: {str(e)}")
            # Если группа не найдена, создаем новую и пробуем снова
            if "404" in str(e) or "500" in str(e):
                group_response = await self.client.create_new_group(access_token, "Telegram")
                user.bothub_group_id = group_response["id"]
                await self.create_new_chat(user, chat, is_image_generation)
            # Если модель не найдена, пробуем создать чат без указания модели
            elif "MODEL_NOT_FOUND" in str(e):
                try:
                    # Создаем чат без указания модели
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        chat_name
                    )
                    chat.bothub_chat_id = response["id"]

                    # Пробуем получить список моделей и выбрать доступную
                    models = await self.client.list_models(access_token)
                    for model in models:
                        if "TEXT_TO_TEXT" in model.get("features", []) and model.get("is_allowed", False):
                            chat.bothub_chat_model = model.get("id")
                            break

                except Exception as inner_e:
                    logger.error(f"Ошибка при создании чата без модели: {str(inner_e)}")
                    raise
            else:
                raise

    async def generate_telegram_connection_link(self, user: User, settings) -> str:
        """
        Генерация ссылки для подключения Telegram к существующему аккаунту BotHub

        Args:
            user: Пользователь
            settings: Настройки приложения

        Returns:
            str: Ссылка для подключения
        """
        try:
            access_token = await self.get_access_token(user)
            token_response = await self.client.generate_telegram_connection_token(access_token)
            token = token_response.get("telegramConnectionToken")

            if not token:
                raise Exception("Не удалось получить токен подключения")

            # Формируем URL для подключения
            web_url = settings.BOTHUB_WEB_URL or "https://bothub.chat"
            return f"{web_url}?telegram-connection-token={token}"
        except Exception as e:
            logger.error(f"Ошибка при генерации ссылки подключения: {str(e)}")
            raise Exception(f"Не удалось создать ссылку подключения: {str(e)}")

    async def reset_context(self, user: User, chat: Chat) -> None:
        """
        Сброс контекста чата

        Args:
            user: Пользователь
            chat: Чат
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.reset_context(access_token, chat.bothub_chat_id)
        chat.reset_context_counter()

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """
        Получение статуса веб-поиска

        Args:
            user: Пользователь
            chat: Чат

        Returns:
            bool: Включен ли веб-поиск
        """
        if not chat.bothub_chat_id:
            return False

        try:
            access_token = await self.get_access_token(user)
            response = await self.client.get_web_search(access_token, chat.bothub_chat_id)
            return response
        except Exception as e:
            logger.error(f"Ошибка при получении статуса веб-поиска: {e}", exc_info=True)
            return False

    async def enable_web_search(self, user: User, chat: Chat, enabled: bool) -> None:
        """
        Включение/выключение веб-поиска

        Args:
            user: Пользователь
            chat: Чат
            enabled: Включить или выключить
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, enabled)


    async def send_message(self, user: User, chat: Chat, message: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Отправка сообщения

        Args:
            user: Пользователь
            chat: Чат
            message: Текст сообщения
            files: Список файлов (URL)

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)

        try:
            response = await self.client.send_message(
                access_token,
                chat.bothub_chat_id,
                message,
                files
            )

            # Увеличиваем счетчик контекста, если надо запоминать его
            if chat.context_remember:
                chat.increment_context_counter()

            return response
        except Exception as e:
            # Если чат не найден, создаем новый
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

    async def save_system_prompt(self, user: User, chat: Chat) -> None:
        """
        Сохранение системного промпта для чата

        Args:
            user: Пользователь
            chat: Чат
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        # Проверяем, что модель поддерживает системные промпты
        # Обычно это GPT модели
        if not chat.bothub_chat_model or "gpt" not in chat.bothub_chat_model.lower():
            return

        # Получаем токен доступа
        access_token = await self.get_access_token(user)

        # Сохраняем системный промпт через API
        await self.client.save_system_prompt(access_token, chat.bothub_chat_id, chat.system_prompt)