from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ImageGenerationUseCase:
    """Юзкейс для работы с генерацией изображений"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def generate_image(self, user: User, chat: Chat, prompt: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Генерация изображения

        Args:
            user: Пользователь
            chat: Чат
            prompt: Запрос для генерации изображения
            files: Список URL файлов (для edit-изображений)

        Returns:
            Dict[str, Any]: Ответ от BotHub API с сгенерированными изображениями
        """
        logger.info(f"Generating image for prompt: {prompt} for user {user.id}")

        # Создаем новый чат для генерации изображений, если текущий чат не для изображений
        current_model = chat.bothub_chat_model
        is_image_generation_model = current_model in ["dall-e", "midjourney", "stability", "kandinsky", "flux"]

        if not is_image_generation_model:
            # Сохраняем текущую модель
            old_model = chat.bothub_chat_model

            # Устанавливаем модель для генерации изображений
            image_model = user.image_generation_model or "dall-e"
            chat.bothub_chat_model = image_model

            # Создаем новый чат
            await self.gateway.create_new_chat(user, chat, True)

            # Генерируем изображение
            result = await self.gateway.send_message(user, chat, prompt, files)

            # Восстанавливаем предыдущую модель и создаем новый чат
            chat.bothub_chat_model = old_model
            await self.gateway.create_new_chat(user, chat)

            return result
        else:
            # Генерируем изображение в текущем чате
            return await self.gateway.send_message(user, chat, prompt, files)

    async def generate_image_without_switching_chat(self, user: User, chat: Chat, prompt: str,
                                                    files: Optional[List[str]] = None) -> Tuple[Dict[str, Any], str]:
        """
        Генерация изображения без видимого переключения чата для пользователя

        Args:
            user: Пользователь
            chat: Чат
            prompt: Запрос для генерации изображения
            files: Список URL файлов (для edit-изображений)

        Returns:
            Tuple[Dict[str, Any], str]: Ответ от BotHub API и используемая модель
        """
        logger.info(f"Seamlessly generating image for prompt: {prompt} for user {user.id}")

        # Сохраняем оригинальные данные чата
        original_chat_id = chat.bothub_chat_id
        original_model = chat.bothub_chat_model

        # Устанавливаем модель для генерации изображений
        image_model = user.image_generation_model
        chat.bothub_chat_model = image_model

        try:
            # Создаем временный чат для генерации изображений
            await self.gateway.create_new_chat(user, chat, True)

            # Генерируем изображение
            result = await self.gateway.send_message(user, chat, prompt, files)

            return result, image_model
        finally:
            # Восстанавливаем оригинальные данные чата
            chat.bothub_chat_id = original_chat_id
            chat.bothub_chat_model = original_model