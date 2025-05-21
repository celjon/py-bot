from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import json
import logging
from ..keyboards.inline_keyboards import get_image_model_inline_keyboard
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat
from aiogram.enums.chat_action import ChatAction

logger = logging.getLogger(__name__)

def register_image_handlers(router: Router, image_generation_usecase, user_repository, chat_repository):
    """Регистрация обработчиков для генерации изображений"""

    @router.message(Command("image_model"))
    async def handle_image_model_command(message: Message):
        """Обработка команды /image_model для выбора модели генерации изображений"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            logger.info(f"Пользователь {user.id} запросил настройку моделей генерации изображений")

            # Получаем доступные модели
            from src.adapter.gateway.bothub_gateway import BothubGateway
            from src.lib.clients.bothub_client import BothubClient
            from src.config.settings import get_settings
            from src.domain.usecase.model_selection import ModelSelectionUseCase

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)
            model_selection_usecase = ModelSelectionUseCase(bothub_gateway)

            # Получаем токен доступа и список моделей
            models = await model_selection_usecase.list_available_models(user)

            # Фильтруем модели для генерации изображений
            image_models = model_selection_usecase.filter_image_models(models)

            if not image_models:
                await message.answer(
                    "⚠️ Не удалось получить список моделей для генерации изображений",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            # Отправляем клавиатуру выбора модели
            keyboard = get_image_model_inline_keyboard(image_models, user.image_generation_model)
            await message.answer(
                "Выберите модель для генерации изображений",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды image_model: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось получить список моделей. Попробуйте позже.",
                parse_mode="Markdown"
            )

    # Обработчик кнопки "Сменить модель изображений"
    @router.message(F.text == "🎨 Сменить модель изображений")
    async def handle_image_model_button(message: Message):
        """Обработка нажатия на кнопку смены модели генерации изображений"""
        await handle_image_model_command(message)

    # Обработчик выбора модели генерации изображений
    @router.callback_query(lambda c: c.data and "img_m" in json.loads(c.data).get("t", ""))
    async def handle_image_model_selection(callback: CallbackQuery):
        try:
            # Декодируем данные callback
            data = json.loads(callback.data)
            model_id = data.get("m")
            is_allowed = data.get("a") == 1

            if not is_allowed:
                await callback.answer("⛔ Эта модель недоступна в вашем тарифе")
                return

            # Получаем пользователя и чат
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Обновляем модель генерации изображений у пользователя
            user.image_generation_model = model_id
            await user_repository.update(user)

            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)

            # Отправляем сообщение об успешном выборе модели
            await callback.message.answer(
                f"✅ Модель *{model_id}* успешно выбрана для генерации изображений.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выбрал модель генерации изображений {model_id}")

        except Exception as e:
            logger.error(f"Ошибка при выборе модели генерации изображений: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выборе модели")