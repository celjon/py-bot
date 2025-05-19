# Обновленный src/delivery/telegram/handlers/account_handlers.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat
from ..services.account_service import AccountService

logger = logging.getLogger(__name__)


async def handle_link_account_logic(message: Message, user_repository, chat_repository, account_connection_usecase):
    """Общая логика для обработки команды привязки аккаунта"""
    user = await get_or_create_user(message, user_repository)
    chat = await get_or_create_chat(user, chat_repository)

    # Генерируем ссылку через сервис
    success, result = await AccountService.generate_connection_link(user, account_connection_usecase)

    if not success:
        # Если ошибка (аккаунт уже привязан или другая ошибка)
        await message.answer(
            result,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user, chat)
        )
        return

    # Если успешно сгенерировали ссылку
    try:
        formatted_message = AccountService.format_connection_message(result)
        await message.answer(
            formatted_message,
            reply_markup=get_main_keyboard(user, chat),
            disable_web_page_preview=False  # Включаем предварительный просмотр чтобы ссылка была кликабельной
        )
        logger.info(f"Пользователь {user.id} запросил ссылку для привязки аккаунта")
    except Exception as format_error:
        logger.error(f"Ошибка форматирования сообщения: {format_error}", exc_info=True)
        # Отправляем ссылку без форматирования
        await message.answer(
            f"Ссылка для привязки аккаунта:\n{result}",
            reply_markup=get_main_keyboard(user, chat)
        )


def register_account_handlers(router: Router, account_connection_usecase, user_repository, chat_repository):
    """Регистрация обработчиков команд аккаунта"""

    @router.message(Command("link_account"))
    async def handle_link_account_command(message: Message):
        """Обработка команды /link_account для привязки аккаунта"""
        try:
            await handle_link_account_logic(message, user_repository, chat_repository, account_connection_usecase)
        except Exception as e:
            logger.error(f"Ошибка при обработке команды link_account: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )