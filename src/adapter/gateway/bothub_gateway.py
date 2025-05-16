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

    # Список доступных моделей в порядке приоритета
    AVAILABLE_MODELS = ["gpt-4.1-nano", "gpt-3.5-turbo", "claude-instant", "gemini-pro"]

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

        return user.bothub_access_token

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
            name = f"Telegram Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Выбор модели в зависимости от типа чата
            if is_image_generation:
                # Логика для создания чата генерации изображений
                if user.image_generation_model and "flux" in user.image_generation_model:
                    # Логика для моделей Flux (аналог PHP-логики)
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        name,
                        "replicate-flux"  # Родительская модель для Flux
                    )

                    # Обновляем родительскую модель
                    await self.client.update_parent_model(
                        access_token,
                        response["id"],
                        "replicate-flux"
                    )

                    # Сохраняем конкретную модель
                    await self.client.save_model(
                        access_token,
                        response["id"],
                        user.image_generation_model
                    )

                    model_id = user.image_generation_model
                else:
                    # Для других моделей генерации изображений
                    model_id = user.image_generation_model or "dall-e"
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        name,
                        model_id
                    )
            else:
                # Логика для создания текстового чата

                # Получаем список доступных моделей
                models = await self.client.list_models(access_token)

                # Выбираем модель по умолчанию, используя логику аналогичную PHP-реализации
                default_model = None
                for model in models:
                    if (model.get("is_default", False) or model.get("is_allowed",
                                                                    True)) and "TEXT_TO_TEXT" in model.get("features",
                                                                                                           []):
                        default_model = model
                        break

                if not default_model:
                    # Если не найдена подходящая модель, используем известные модели
                    for backup_model_id in ["gpt-4o", "gpt-3.5-turbo", "claude-3-haiku"]:
                        for model in models:
                            if model.get("id") == backup_model_id and model.get("is_allowed", False):
                                default_model = model
                                break
                        if default_model:
                            break

                if not default_model:
                    # Если все еще не найдена модель, используем первую доступную
                    for model in models:
                        if model.get("is_allowed", False) and "TEXT_TO_TEXT" in model.get("features", []):
                            default_model = model
                            break

                if default_model:
                    model_id = default_model.get("id")
                    parent_id = default_model.get("parent_id")

                    # Создаем чат с родительской моделью
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        name,
                        parent_id or model_id
                    )

                    # Проверяем, нужно ли применять особые настройки для чата
                    should_save_settings = (
                            (chat.bothub_chat_model and chat.bothub_chat_model != model_id) or
                            not chat.context_remember or
                            chat.system_prompt
                    )

                    if should_save_settings:
                        # Определяем максимальное количество токенов
                        max_tokens = None
                        if chat.bothub_chat_model:
                            # Проверяем, не является ли модель моделью для генерации изображений
                            model_is_text = True  # здесь нужна функция проверки типа модели
                            for m in models:
                                if m.get("id") == chat.bothub_chat_model:
                                    if "TEXT_TO_IMAGE" in m.get("features", []):
                                        model_is_text = False
                                    break

                            if model_is_text:
                                # Если есть модель и это текстовая модель
                                model_to_use = None
                                for m in models:
                                    if m.get("id") == chat.bothub_chat_model:
                                        model_to_use = m
                                        break

                                if model_to_use:
                                    model_id = model_to_use.get("id")
                                    # Устанавливаем максимальное количество токенов
                                    if "max_tokens" in model_to_use:
                                        max_tokens = int(model_to_use.get("max_tokens") / 2)

                        # Сохраняем настройки чата
                        await self.client.save_chat_settings(
                            access_token,
                            response["id"],
                            model_id,
                            max_tokens,
                            chat.context_remember,
                            chat.system_prompt
                        )
                else:
                    # Если не найдена ни одна модель, создаем чат без указания модели
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        name
                    )
                    model_id = None

            # Обновляем данные чата
            chat.bothub_chat_id = response["id"]
            if model_id:
                chat.bothub_chat_model = model_id

        except Exception as e:
            logger.error(f"Ошибка при создании чата: {str(e)}")

            # Если группа не найдена или возникла ошибка 500, создаем новую и пробуем снова
            if "404" in str(e) or "500" in str(e):
                group_response = await self.client.create_new_group(access_token, "Telegram")
                user.bothub_group_id = group_response["id"]
                await self.create_new_chat(user, chat, is_image_generation)
            else:
                raise Exception(f"Не удалось создать чат: {str(e)}")


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

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """
        Получение статуса веб-поиска для чата

        Args:
            user: Пользователь
            chat: Чат

        Returns:
            bool: Включен ли веб-поиск
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

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

    async def save_system_prompt(self, user: User, chat: Chat) -> None:
        """
        Сохранение системного промпта

        Args:
            user: Пользователь
            chat: Чат
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.save_system_prompt(access_token, chat.bothub_chat_id, chat.system_prompt)

    async def generate_telegram_connection_link(self, user: User, settings) -> str:
        """
        Генерация ссылки для подключения Telegram к аккаунту

        Args:
            user: Пользователь
            settings: Настройки приложения

        Returns:
            str: Ссылка для подключения
        """
        access_token = await self.get_access_token(user)
        response = await self.client.generate_telegram_connection_token(access_token)
        token = response.get("telegramConnectionToken", "")

        web_url = settings.BOTHUB_WEB_URL
        return f"{web_url}?telegram-connection-token={token}"

    async def transcribe_voice(self, user: User, chat: Chat, file_path: str) -> str:
        """
        Транскрибирование голосового сообщения

        Args:
            user: Пользователь
            chat: Чат
            file_path: Путь к аудиофайлу

        Returns:
            str: Транскрибированный текст
        """
        access_token = await self.get_access_token(user)
        return await self.client.whisper(access_token, file_path)