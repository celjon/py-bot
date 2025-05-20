# src/delivery/telegram/handlers/config_handlers.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums.chat_action import ChatAction
import logging
from ..services.keyboard_factory import KeyboardFactory
from ..services.callback_data import CallbackData
from ..services.callback_types import CallbackType
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, get_or_create_user_from_callback
from ..services.model_service import show_model_selection
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.lib.clients.bothub_client import BothubClient
from src.config.settings import get_settings
from src.domain.usecase.chat_session import ChatSessionUseCase

logger = logging.getLogger(__name__)


def register_config_handlers(router: Router, user_repository, chat_repository):
    """Регистрация обработчиков команд конфигурации"""

    @router.message(Command("gpt_config"))
    async def handle_gpt_config(message: Message):
        """Обработка команды /gpt_config для настройки моделей"""
        await show_model_selection(message, user_repository, chat_repository)

    def callback_with_type(callback_type):
        async def check(callback: CallbackQuery):
            try:
                data = CallbackData.decode(callback.data)
                return data.type == callback_type
            except:
                return False

        return check

    @router.callback_query(callback_with_type(CallbackType.MODEL_SELECTION))
    async def handle_model_selection(callback: CallbackQuery):
        try:
            data = CallbackData.decode(callback.data)
            model_id = data.data.get("id")

            # ИСПРАВЛЕНИЕ: Используем функцию для callback!
            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            chat.bothub_chat_model = model_id
            chat.reset_context_counter()
            user.gpt_model = model_id

            await user_repository.update(user)
            await chat_repository.update(chat)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"Выбрана модель *{model_id}*. Создаю новый чат...")

            await callback.message.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)
            chat_session = ChatSessionUseCase(bothub_gateway)

            await chat_session.create_new_chat(user, chat)

            model_info = f"Начат новый чат с моделью *{model_id}*"
            context_info = "\n\nКонтекст включен. /reset для сброса." if chat.context_remember else "\n\nКонтекст отключен."

            await callback.message.answer(
                f"{model_info}{context_info}",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выбрал модель {model_id}")

        except Exception as e:
            logger.error(f"Ошибка при выборе модели: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выборе модели")

    @router.callback_query(callback_with_type(CallbackType.UNAVAILABLE_MODEL))
    async def handle_unavailable_model(callback: CallbackQuery):
        await callback.answer("⛔ Эта модель недоступна в вашем тарифе")

    @router.callback_query(callback_with_type(CallbackType.CANCEL))
    async def handle_cancel(callback: CallbackQuery):
        try:
            # ИСПРАВЛЕНИЕ: Используем функцию для callback!
            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Операция отменена", reply_markup=get_main_keyboard(user, chat))
        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}", exc_info=True)
            await callback.answer("Произошла ошибка")