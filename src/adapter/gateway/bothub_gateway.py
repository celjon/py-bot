from typing import Dict, Any, Optional, List, Tuple
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """
        Получение/обновление токена доступа

        Returns:
            Tuple[str, Optional[str], Optional[str], Optional[str]]:
                (access_token, group_id, chat_id, model_id)
        """
        if user.bothub_access_token:
            # Проверка срока действия токена (по умолчанию - 24 часа)
            token_lifetime = 86390  # 24 * 60 * 60 - 10 секунд
            current_time = datetime.now()

            if (user.bothub_access_token_created_at and
                    (current_time - user.bothub_access_token_created_at).total_seconds() < token_lifetime):
                logger.debug(f"Using existing token for user {user.id}")
                return (user.bothub_access_token, user.bothub_group_id,
                        None, None)

        logger.info(f"Getting new access token for user {user.id}")
        response = await self.client.authorize(
            user.telegram_id,
            user.first_name or user.username or "Telegram User",
            user.bothub_id,
            user.referral_code
        )

        # Обновляем информацию о пользователе
        user.bothub_access_token = response["accessToken"]
        user.bothub_access_token_created_at = datetime.now()

        if not user.bothub_id:
            user.bothub_id = response["user"]["id"]

        # Проверяем наличие групп и чатов у пользователя
        group_id = None
        chat_id = None
        model_id = None

        if "groups" in response["user"] and response["user"]["groups"]:
            groups = response["user"]["groups"]
            group_id = groups[0]["id"]
            user.bothub_group_id = group_id

            if groups[0]["chats"]:
                chats = groups[0]["chats"]
                chat_id = chats[0]["id"]

                if "settings" in chats[0] and "model" in chats[0]["settings"]:
                    model_id = chats[0]["settings"]["model"]

        return user.bothub_access_token, group_id, chat_id, model_id

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """Создание нового чата"""
        access_token, group_id, _, _ = await self.get_access_token(user)

        if not group_id:
            logger.info(f"Creating new group for user {user.id}")
            group_response = await self.client.create_new_group(access_token, "Telegram")
            group_id = group_response["id"]
            user.bothub_group_id = group_id

        # Определяем модель в зависимости от типа чата
        model_id = None
        if is_image_generation:
            model_id = user.image_generation_model or "dall-e"
        else:
            model_id = user.gpt_model or "gpt-3.5-turbo"

        # Получаем список доступных моделей для валидации
        try:
            models = await self.client.list_models(access_token)
            available_models = [model["id"] for model in models]

            # Проверяем, что модель доступна
            if model_id not in available_models:
                logger.warning(f"Model {model_id} not available, using default")
                default_models = [model for model in models if model.get('is_default')]
                if default_models:
                    model_id = default_models[0]["id"]
                else:
                    model_id = models[0]["id"] if models else "gpt-3.5-turbo"
        except Exception as e:
            logger.error(f"Error getting models list: {str(e)}")
            # Используем модель по умолчанию
            model_id = "gpt-3.5-turbo" if not is_image_generation else "dall-e"

        logger.info(f"Creating new chat for user {user.id} with model {model_id}")
        response = await self.client.create_new_chat(
            access_token,
            group_id,
            f"Telegram chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            model_id
        )

        chat.bothub_chat_id = response["id"]
        chat.bothub_chat_model = response.get("model_id", model_id)

        # Если нужны дополнительные настройки чата
        if chat.system_prompt or not chat.context_remember:
            await self.save_chat_settings(user, chat)

    async def save_chat_settings(self, user: User, chat: Chat) -> None:
        """Сохранение настроек чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)

        # Определяем максимальное количество токенов в зависимости от модели
        max_tokens = None
        if "gpt-4" in chat.bothub_chat_model:
            max_tokens = 4000
        elif "gpt-3.5" in chat.bothub_chat_model:
            max_tokens = 2000

        await self.client.save_chat_settings(
            access_token,
            chat.bothub_chat_id,
            chat.bothub_chat_model,
            max_tokens,
            chat.context_remember,
            chat.system_prompt
        )

    async def reset_context(self, user: User, chat: Chat) -> None:
        """Сброс контекста чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        await self.client.reset_context(access_token, chat.bothub_chat_id)
        chat.reset_context_counter()

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """Проверка статуса веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

    async def enable_web_search(self, user: User, chat: Chat, value: bool) -> None:
        """Включение/выключение веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, value)

    async def send_message(self, user: User, chat: Chat, message: str, files: List = None) -> Dict[str, Any]:
        """Отправка сообщения"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)

        try:
            response = await self.client.send_message(access_token, chat.bothub_chat_id, message, files)

            # Обновляем счетчик контекста, если надо запоминать его
            if chat.context_remember:
                chat.increment_context_counter()

            return response
        except Exception as e:
            # Если чат не найден, создаем новый
            if "CHAT_NOT_FOUND" in str(e):
                logger.warning(f"Chat not found, creating new one for user {user.id}")
                await self.create_new_chat(user, chat)
                return await self.client.send_message(access_token, chat.bothub_chat_id, message, files)
            raise

    async def send_buffer(self, user: User, chat: Chat) -> Dict[str, Any]:
        """Отправка буфера сообщений"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)

        # Собираем все тексты из буфера
        buffer_messages = chat.buffer.get("messages", [])
        texts = []
        files = []

        for buffer_message in buffer_messages:
            if "text" in buffer_message:
                texts.append(buffer_message["text"])

            # TODO: Обработка файлов

        # Объединяем тексты
        message = "\n".join(texts)

        try:
            response = await self.client.send_message(access_token, chat.bothub_chat_id, message, files)

            # Обновляем счетчик контекста, если надо запоминать его
            if chat.context_remember:
                chat.increment_context_counter()

            # Сбрасываем буфер
            chat.refresh_buffer()

            return response
        except Exception as e:
            # Если чат не найден, создаем новый
            if "CHAT_NOT_FOUND" in str(e):
                logger.warning(f"Chat not found, creating new one for user {user.id}")
                await self.create_new_chat(user, chat)
                return await self.client.send_message(access_token, chat.bothub_chat_id, message, files)
            raise