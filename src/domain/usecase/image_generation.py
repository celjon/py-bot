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
        """
        logger.info(f"🎨 Запуск процесса генерации изображения для пользователя {user.id}")
        logger.info(f"🎨 Промпт для генерации: '{prompt}'")
        logger.info(f"🎨 Текущая модель чата: '{chat.bothub_chat_model}'")
        logger.info(f"🎨 Модель для генерации изображений: '{user.image_generation_model}'")

        # Сохраняем оригинальные данные чата
        original_chat_id = chat.bothub_chat_id
        original_model = chat.bothub_chat_model
        logger.info(f"🎨 Сохранение оригинального ID чата: {original_chat_id}")
        logger.info(f"🎨 Сохранение оригинальной модели: {original_model}")

        try:
            # Получаем доступные модели для генерации изображений
            access_token = await self.gateway.get_access_token(user)
            models = await self.gateway.client.list_models(access_token)

            # Фильтруем модели для генерации изображений
            image_models = [model for model in models if "TEXT_TO_IMAGE" in model.get("features", [])]
            available_image_models = [model for model in image_models if model.get("is_allowed", True)]

            logger.info(f"🎨 Найдено {len(available_image_models)} доступных моделей для генерации изображений")

            # Проверяем наличие доступных моделей
            if not available_image_models:
                logger.warning(f"🎨 Нет доступных моделей для генерации изображений")
                raise Exception("MODEL_NOT_FOUND: У вас нет доступа к моделям генерации изображений")

            # Выбираем модель - сначала проверяем текущую модель пользователя
            chosen_model = None
            if user.image_generation_model:
                for model in available_image_models:
                    if model["id"] == user.image_generation_model:
                        chosen_model = model["id"]
                        break

            # Если модель не выбрана или недоступна, берем первую доступную
            if not chosen_model:
                chosen_model = available_image_models[0]["id"]
                # Сохраняем выбранную модель для пользователя
                user.image_generation_model = chosen_model
                try:
                    from src.adapter.repository.user_repository import UserRepository
                    user_repo = UserRepository()
                    await user_repo.update(user)
                    logger.info(f"🎨 Автоматически выбрана модель: {chosen_model}")
                except Exception as e:
                    logger.error(f"🎨 Ошибка при обновлении модели пользователя: {e}")

            # ИСПРАВЛЕНИЕ: Устанавливаем выбранную модель в чат ДО создания
            chat.bothub_chat_model = chosen_model
            logger.info(f"🎨 Установка модели для генерации изображений: {chosen_model}")

            # Создаем чат с флагом is_image_generation=True
            await self.gateway.create_new_chat(user, chat, is_image_generation=True)
            logger.info(f"🎨 Чат для генерации изображений создан с ID: {chat.bothub_chat_id}")

            # Генерируем изображение - с детальным логированием ответа
            logger.info(f"🎨 Отправка запроса на генерацию изображения с промптом: '{prompt}'")
            result = await self.gateway.send_message(user, chat, prompt, files)
            
            # Обрабатываем возможную ошибку rate limit
            if 'error' in result and result['error'] == 'FLOOD_ERROR':
                wait_time = result.get('wait_time', 60)
                logger.warning(f"🎨 Получена ошибка rate limit. Требуется подождать {wait_time} секунд.")
                
                # Пропускаем повторные попытки при ошибке rate limit
                return {
                    "response": {
                        "content": f"Слишком много запросов. Пожалуйста, подождите {wait_time} секунд и попробуйте снова."
                    },
                    "error": "FLOOD_ERROR"
                }, chosen_model
            
            logger.info(f"🎨 Получен ответ от API: {result}")

            return result, chosen_model
        except Exception as e:
            logger.error(f"🎨 Ошибка при генерации изображения: {e}", exc_info=True)
            raise
        finally:
            # Восстанавливаем оригинальные данные чата
            logger.info(f"🎨 Восстановление оригинального ID чата: {original_chat_id}")
            logger.info(f"🎨 Восстановление оригинальной модели: {original_model}")
            chat.bothub_chat_id = original_chat_id
            chat.bothub_chat_model = original_model