# src/domain/usecase/model_selection.py
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ModelSelectionUseCase:
    """Юзкейс для выбора моделей AI"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def list_available_models(self, user: User) -> List[Dict[str, Any]]:
        """
        Получение списка доступных моделей

        Args:
            user: Пользователь

        Returns:
            List[Dict[str, Any]]: Список моделей
        """
        logger.info(f"Получение списка моделей для пользователя {user.id}")
        try:
            access_token = await self.gateway.get_access_token(user)
            models = await self.gateway.client.list_models(access_token)
            return models
        except Exception as e:
            logger.error(f"Ошибка при получении списка моделей: {e}", exc_info=True)
            raise Exception(f"Не удалось получить список моделей: {e}")

    async def select_chat_model(self, user: User, chat: Chat, model_id: str) -> None:
        """
        Выбор модели для чата

        Args:
            user: Пользователь
            chat: Чат
            model_id: ID модели
        """
        logger.info(f"Выбор модели {model_id} для чата пользователя {user.id}")

        # Сохраняем модель в чате и сбрасываем счетчик контекста
        chat.bothub_chat_model = model_id
        chat.reset_context_counter()

        # Сохраняем модель как предпочтительную для пользователя
        user.gpt_model = model_id

        # Создаем новый чат с выбранной моделью
        try:
            await self.gateway.create_new_chat(user, chat)
            logger.info(f"Новый чат создан с моделью {model_id}")
        except Exception as e:
            logger.error(f"Ошибка при создании нового чата с моделью {model_id}: {e}", exc_info=True)
            raise Exception(f"Не удалось создать новый чат: {e}")

    async def select_image_model(self, user: User, model_id: str) -> None:
        """
        Выбор модели для генерации изображений

        Args:
            user: Пользователь
            model_id: ID модели
        """
        logger.info(f"Выбор модели {model_id} для генерации изображений для пользователя {user.id}")

        # Сохраняем модель как предпочтительную для генерации изображений
        user.image_generation_model = model_id

    def is_text_model(self, model_id: str) -> bool:
        """
        Проверка, является ли модель текстовой

        Args:
            model_id: ID модели

        Returns:
            bool: True, если модель текстовая
        """
        # Примеры текстовых моделей: gpt-3.5, gpt-4, claude-instant
        text_model_prefixes = ['gpt-', 'claude-', 'llama-', 'gpt4']
        return any(model_id.startswith(prefix) for prefix in text_model_prefixes)

    def is_image_model(self, model_id: str) -> bool:
        """
        Проверка, является ли модель для генерации изображений

        Args:
            model_id: ID модели

        Returns:
            bool: True, если модель для генерации изображений
        """
        # Примеры моделей для генерации изображений: dall-e, midjourney, stable-diffusion
        image_models = ['dall-e', 'midjourney', 'stable-diffusion', 'kandinsky', 'flux']
        return any(model_id == model or model_id.startswith(model) for model in image_models)

    def filter_text_models(self, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Фильтрация списка моделей для получения только текстовых моделей

        Args:
            models: Список моделей

        Returns:
            List[Dict[str, Any]]: Отфильтрованный список моделей
        """
        return [model for model in models if "TEXT_TO_TEXT" in model.get("features", [])]

    def filter_image_models(self, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Фильтрация списка моделей для получения только моделей генерации изображений

        Args:
            models: Список моделей

        Returns:
            List[Dict[str, Any]]: Отфильтрованный список моделей
        """
        return [model for model in models if "TEXT_TO_IMAGE" in model.get("features", [])]