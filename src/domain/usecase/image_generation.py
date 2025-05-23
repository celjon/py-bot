# src/domain/usecase/image_generation.py
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

    async def generate_image_without_switching_chat(self, user: User, chat: Chat, prompt: str,
                                                    files: Optional[List[str]] = None) -> Tuple[Dict[str, Any], str]:
        """
        Генерация изображения без видимого переключения чата для пользователя
        """
        logger.info(f"🎨 Запуск процесса генерации изображения для пользователя {user.id}")
        logger.info(f"🎨 Промпт для генерации: '{prompt}'")

        # Сохраняем оригинальные данные чата
        original_chat_id = chat.bothub_chat_id
        original_model = chat.bothub_chat_model

        try:
            # Определяем модель для генерации изображений
            image_model = user.image_generation_model or "dall-e"

            # Устанавливаем модель в чат перед созданием
            chat.bothub_chat_model = image_model

            # Создаем новый чат специально для генерации изображений
            # Это аналог PHP: $this->createNewChat($userChat, true) где true = imageGeneration
            await self.gateway.create_new_chat(user, chat, is_image_generation=True)

            logger.info(f"🎨 Чат для генерации изображений создан с ID: {chat.bothub_chat_id}")
            logger.info(f"🎨 Используется модель: {chat.bothub_chat_model}")

            # Отправляем запрос на генерацию ОДИН РАЗ
            logger.info(f"🎨 Отправка ЕДИНСТВЕННОГО запроса на генерацию")
            result = await self.gateway.send_message(user, chat, prompt, files)

            logger.info(f"🎨 Получен ответ от сервера")

            return result, image_model

        except Exception as e:
            logger.error(f"🎨 Ошибка при генерации изображения: {e}", exc_info=True)
            raise
        finally:
            # Восстанавливаем оригинальные данные чата
            logger.info(f"🎨 Восстановление оригинального состояния чата")
            chat.bothub_chat_id = original_chat_id
            chat.bothub_chat_model = original_model

    async def generate_image(self, user: User, chat: Chat, prompt: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Генерация изображения с переключением модели
        """
        logger.info(f"Generating image for prompt: {prompt} for user {user.id}")

        # Используем новый метод без видимого переключения
        result, model = await self.generate_image_without_switching_chat(user, chat, prompt, files)
        return result