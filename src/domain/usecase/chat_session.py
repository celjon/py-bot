from typing import Dict, Any, Optional
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.domain.entity.message import Message
from src.adapter.gateway.bothub_gateway import BothubGateway


class ChatSessionUseCase:
    """Юзкейс для обычного чата с ИИ"""

    def __init__(self, bothub_gateway: BothubGateway):
        self.bothub_gateway = bothub_gateway

    async def send_message(
            self,
            user: User,
            chat: Chat,
            message: str,
            files: Optional[list] = None
    ) -> Dict[str, Any]:
        """Отправляет сообщение в обычный чат и получает ответ"""
        # Проверяем, существует ли чат, если нет - создаем
        if not chat.bothub_chat_id:
            await self.bothub_gateway.create_new_chat(user, chat)

        # Если чат поддерживает контекст, увеличиваем счетчик
        if chat.context_remember:
            chat.context_counter += 1

        # Отправляем сообщение и получаем ответ
        response = await self.bothub_gateway.send_message(user, chat, message, files)

        return response