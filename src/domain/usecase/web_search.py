from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway

class WebSearchUseCase:
    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def search(self, user: User, chat: Chat, query: str, files: list = None) -> dict:
        return {"response": {"content": "Результаты поиска недоступны (заглушка)"}}