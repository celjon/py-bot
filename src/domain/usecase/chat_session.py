from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ChatSessionUseCase:
    """Юзкейс для работы с чат-сессиями"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def send_message(self, user: User, chat: Chat, message: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Отправка сообщения в чат

        Args:
            user: Пользователь
            chat: Чат
            message: Текст сообщения
            files: Список URL файлов

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        logger.info(f"Sending message to chat {chat.bothub_chat_id} for user {user.id}")
        return await self.gateway.send_message(user, chat, message, files)

    async def send_buffer(self, user: User, chat: Chat) -> Dict[str, Any]:
        """
        Отправка буфера сообщений

        Args:
            user: Пользователь
            chat: Чат

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        logger.info(f"Sending buffer to chat {chat.bothub_chat_id} for user {user.id}")
        return await self.gateway.send_buffer(user, chat)

    async def reset_context(self, user: User, chat: Chat) -> None:
        """
        Сброс контекста чата

        Args:
            user: Пользователь
            chat: Чат
        """
        logger.info(f"Resetting context for chat {chat.bothub_chat_id} for user {user.id}")
        await self.gateway.reset_context(user, chat)

    async def save_system_prompt(self, user: User, chat: Chat) -> None:
        """
        Сохранение системного промпта чата

        Args:
            user: Пользователь
            chat: Чат
        """
        logger.info(f"Saving system prompt for chat {chat.bothub_chat_id} for user {user.id}")
        await self.gateway.save_chat_settings(user, chat)

    async def transcribe_voice(self, user: User, chat: Chat, file_url: str) -> str:
        """
        Транскрибирование голосового сообщения

        Args:
            user: Пользователь
            chat: Чат
            file_url: URL файла голосового сообщения

        Returns:
            str: Текст голосового сообщения
        """
        # TODO: Реализовать метод в BothubGateway
        logger.info(f"Transcribing voice message for user {user.id}")
        # Временное решение
        return "Это текст голосового сообщения (заглушка)"