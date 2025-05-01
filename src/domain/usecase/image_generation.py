from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway

class ImageGenerationUseCase:
    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def generate_image(self, user: User, chat: Chat, prompt: str, files: list = None) -> dict:
        return {"response": {"attachments": []}}