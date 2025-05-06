# src/domain/usecase/web_search.py

from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class WebSearchUseCase:
    """Юзкейс для работы с веб-поиском"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def search(self, user: User, chat: Chat, query: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Поиск информации в интернете

        Args:
            user: Пользователь
            chat: Чат
            query: Поисковый запрос
            files: Список URL файлов

        Returns:
            Dict[str, Any]: Ответ от BotHub API с результатами поиска
        """
        logger.info(f"Searching web for query: {query} for user {user.id}")

        # Включаем веб-поиск для чата, если он не включен
        try:
            web_search_enabled = await self.gateway.get_web_search(user, chat)
            if not web_search_enabled:
                await self.gateway.enable_web_search(user, chat, True)
                logger.info(f"Web search enabled for chat {chat.bothub_chat_id}")
        except Exception as e:
            logger.error(f"Error enabling web search: {e}", exc_info=True)

        # Формируем запрос с явным указанием на поиск
        search_query = f"web search: {query}"

        return await self.gateway.send_message(user, chat, search_query, files)

    async def toggle_web_search(self, user: User, chat: Chat, enabled: bool) -> None:
        """
        Включение/выключение веб-поиска

        Args:
            user: Пользователь
            chat: Чат
            enabled: Включен ли веб-поиск
        """
        logger.info(f"Toggling web search to {enabled} for chat {chat.bothub_chat_id}")
        await self.gateway.enable_web_search(user, chat, enabled)