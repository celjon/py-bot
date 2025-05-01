from typing import Dict, Any, Optional
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway


class ImageGenerationUseCase:
    """Юзкейс для генерации изображений"""

    def __init__(self, bothub_gateway: BothubGateway):
        self.bothub_gateway = bothub_gateway

    async def generate_image(
            self,
            user: User,
            chat: Chat,
            prompt: str,
            files: Optional[list] = None
    ) -> Dict[str, Any]:
        """Генерирует изображение на основе текстового запроса"""
        # Создаем новый чат для генерации изображений, если не существует
        if not chat.bothub_chat_id or chat.bothub_chat_model != "midjourney":
            # Сохраняем текущий ID чата, если есть
            old_chat_id = chat.bothub_chat_id

            # Создаем новый чат для генерации изображений
            await self.bothub_gateway.create_new_chat(user, chat, image_generation=True)

            # Если был старый чат, записываем его ID для возможного восстановления
            if old_chat_id:
                pass  # TODO: сохранить старый ID для возможного переключения обратно

        # Отправляем запрос на генерацию изображения
        response = await self.bothub_gateway.send_message(user, chat, prompt, files)

        return response