# src/delivery/telegram/handlers/config_handlers.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import logging
from ..services.keyboard_factory import KeyboardFactory
from ..services.callback_data import CallbackData
from ..services.callback_types import CallbackType
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

logger = logging.getLogger(__name__)


def register_config_handlers(router: Router, user_repository, chat_repository):
    """Регистрация обработчиков команд конфигурации"""

    @router.message(Command("gpt_config"))
    async def handle_gpt_config(message: Message):
        """Обработка команды /gpt_config для настройки моделей"""
        try:
            # Получаем пользователя и чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            logger.info(f"Пользователь {user.id} запросил настройку GPT моделей")

            # Получаем доступные модели
            from src.adapter.gateway.bothub_gateway import BothubGateway
            from src.lib.clients.bothub_client import BothubClient
            from src.config.settings import get_settings

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)

            # Получаем токен доступа и список моделей
            access_token = await bothub_gateway.get_access_token(user)
            models = await bothub_client.list_models(access_token)

            # Фильтруем текстовые модели
            text_models = [
                model for model in models
                if "TEXT_TO_TEXT" in model.get("features", [])
            ]

            if not text_models:
                await message.answer(
                    "⚠️ Не удалось получить список моделей",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            # Отправляем клавиатуру выбора модели
            keyboard = KeyboardFactory.create_model_selection(text_models, chat.bothub_chat_model)
            await message.answer(
                "Выберите модель ChatGPT",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды gpt_config: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось получить список моделей. Попробуйте позже.",
                parse_mode="Markdown"
            )

    # Создаем функцию для проверки типа callback
    def callback_with_type(callback_type):
        async def check(callback: CallbackQuery):
            try:
                data = CallbackData.decode(callback.data)
                return data.type == callback_type
            except:
                return False

        return check

    # Обработчик для выбора модели
    @router.callback_query(callback_with_type(CallbackType.MODEL_SELECTION))
    async def handle_model_selection(callback: CallbackQuery):
        try:
            # Декодируем данные callback
            data = CallbackData.decode(callback.data)
            model_id = data.data.get("id")

            # Получаем пользователя и чат
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Обновляем модель
            chat.bothub_chat_model = model_id
            chat.reset_context_counter()
            user.gpt_model = model_id

            await user_repository.update(user)
            await chat_repository.update(chat)

            # Создаем новый чат с выбранной моделью
            from src.adapter.gateway.bothub_gateway import BothubGateway
            from src.lib.clients.bothub_client import BothubClient
            from src.config.settings import get_settings

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)

            await bothub_gateway.create_new_chat(user, chat)

            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)

            # Отправляем сообщение об успешном выборе модели
            await callback.message.answer(
                f"✅ Модель *{model_id}* успешно выбрана. Начните новый чат, чтобы изменения вступили в силу.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выбрал модель {model_id}")

        except Exception as e:
            logger.error(f"Ошибка при выборе модели: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выборе модели")

    # Обработчик для недоступных моделей
    @router.callback_query(callback_with_type(CallbackType.UNAVAILABLE_MODEL))
    async def handle_unavailable_model(callback: CallbackQuery):
        await callback.answer("⛔ Эта модель недоступна в вашем тарифе")

    # Обработчик для отмены
    @router.callback_query(callback_with_type(CallbackType.CANCEL))
    async def handle_cancel(callback: CallbackQuery):
        try:
            # Получаем пользователя и чат
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Удаляем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)

            # Отправляем сообщение
            await callback.message.answer(
                "Операция отменена",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}", exc_info=True)
            await callback.answer("Произошла ошибка")