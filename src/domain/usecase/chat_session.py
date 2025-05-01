from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway

class ChatSessionUseCase:
    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def send_message(self, user: User, chat: Chat, message: str, files: list = None) -> dict:
        return {"response": {"content": f"Эхо: {message}"}}