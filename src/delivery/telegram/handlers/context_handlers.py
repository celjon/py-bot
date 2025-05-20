# src/delivery/telegram/handlers/context_handlers.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import json
import logging
from ..keyboards.inline_keyboards import get_context_inline_keyboard
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, get_or_create_user_from_callback

logger = logging.getLogger(__name__)

def register_context_handlers(router: Router, chat_session_usecase, user_repository, chat_repository):
    """Регистрация обработчиков для управления контекстом"""

    @router.message(Command("context"))
    async def handle_context_command(message: Message):
        """Обработка команды /context для настройки контекста"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            await message.answer(
                "Должен ли бот запоминать контекст чатов?",
                parse_mode="Markdown",
                reply_markup=get_context_inline_keyboard(chat.context_remember)
            )

            logger.info(f"Пользователь {user.id} запросил настройку контекста")

        except Exception as e:
            logger.error(f"Ошибка при обработке команды context: {e}", exc_info=True)
            await message.answer("❌ Не удалось обработать команду. Попробуйте позже.")

    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "ctx" and json.loads(c.data).get("a") == "on")
    async def handle_context_on(callback: CallbackQuery):
        """Обработка включения контекста"""
        try:
            # ИСПРАВЛЕНИЕ: Используем функцию для callback!
            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            chat.context_remember = True
            await chat_repository.update(chat)

            await chat_session_usecase.create_new_chat(user, chat)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Запоминание контекста включено")

            await callback.message.answer(
                "✅ Запоминание контекста включено. Теперь я буду помнить историю нашего диалога.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} включил запоминание контекста")

        except Exception as e:
            logger.error(f"Ошибка при включении контекста: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при включении контекста")

    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "ctx" and json.loads(c.data).get("a") == "off")
    async def handle_context_off(callback: CallbackQuery):
        """Обработка выключения контекста"""
        try:
            # ИСПРАВЛЕНИЕ: Используем функцию для callback!
            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            chat.context_remember = False
            chat.reset_context_counter()
            await chat_repository.update(chat)

            await chat_session_usecase.create_new_chat(user, chat)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Запоминание контекста выключено")

            await callback.message.answer(
                "✅ Запоминание контекста выключено. Теперь каждое сообщение будет рассматриваться отдельно.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выключил запоминание контекста")

        except Exception as e:
            logger.error(f"Ошибка при выключении контекста: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выключении контекста")