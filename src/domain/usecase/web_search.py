from typing import Dict, Any, Optional
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway


class WebSearchUseCase:
    """Юзкейс для поиска в интернете"""

    def __init__(self, bothub_gateway: BothubGateway):
        self.bothub_gateway = bothub_gateway

    async def search(
            self,
            user: User,
            chat: Chat,
            query: str,
            files: Optional[list] = None
    ) -> Dict[str, Any]:
        """Выполняет поиск в интернете и получает ответ"""
        # Проверяем, существует ли чат, если нет - создаем
        if not chat.bothub_chat_id:
            await self.bothub_gateway.create_new_chat(user, chat)

        # Включаем веб-поиск для чата, если еще не включен
        current_web_search = await self.bothub_gateway.get_web_search(user, chat)
        if not current_web_search:
            await self.bothub_gateway.enable_web_search(user, chat, True)

        # Если чат поддерживает контекст, увеличиваем счетчик
        if chat.context_remember:
            chat.context_counter += 1

        # Отправляем запрос и получаем ответ
        response = await self.bothub_gateway.send_message(user, chat, query, files)

        return response