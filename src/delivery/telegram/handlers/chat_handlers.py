from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

logger = logging.getLogger(__name__)


def register_chat_handlers(router: Router, chat_session_usecase, user_repository, chat_repository):
    """Регистрация обработчиков команд чата"""

    @router.message(Command("reset"))
    async def handle_reset_command(message: Message):
        """Обработка команды /reset для сброса контекста"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Демо-версия: просто сбрасываем счетчик
            chat.reset_context_counter()
            await chat_repository.update(chat)

            # В полной версии будет вызов
            # await chat_session_usecase.reset_context(user, chat)

            await message.answer(
                "🔄 Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} сбросил контекст чата {chat.id}")

        except Exception as e:
            logger.error(f"Ошибка сброса контекста: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
                parse_mode="Markdown"
            )