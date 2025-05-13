from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import json
import logging
from ..keyboards.inline_keyboards import get_context_inline_keyboard
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

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
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "ctx" and json.loads(c.data).get("a") == "on")
    async def handle_context_on(callback: CallbackQuery):
        """Обработка включения контекста"""
        try:
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Включаем запоминание контекста
            chat.context_remember = True
            await chat_repository.update(chat)

            # Создаем новый чат с включенным контекстом
            await chat_session_usecase.create_new_chat(user, chat)

            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Запоминание контекста включено")

            # Отправляем сообщение
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
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Выключаем запоминание контекста
            chat.context_remember = False
            chat.reset_context_counter()
            await chat_repository.update(chat)

            # Создаем новый чат с выключенным контекстом
            await chat_session_usecase.create_new_chat(user, chat)

            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Запоминание контекста выключено")

            # Отправляем сообщение
            await callback.message.answer(
                "✅ Запоминание контекста выключено. Теперь каждое сообщение будет рассматриваться отдельно.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выключил запоминание контекста")

        except Exception as e:
            logger.error(f"Ошибка при выключении контекста: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выключении контекста")

    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "c")
    async def handle_cancel(callback: CallbackQuery):
        """Обработка отмены действия"""
        try:
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Операция отменена")

            # Отправляем сообщение
            await callback.message.answer(
                "Операция отменена",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} отменил операцию")

        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при отмене")