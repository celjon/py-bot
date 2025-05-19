from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

logger = logging.getLogger(__name__)


def register_account_handlers(router: Router, account_connection_usecase, user_repository, chat_repository):
    """Регистрация обработчиков команд аккаунта"""

    @router.message(Command("link_account"))
    async def handle_link_account_command(message: Message):
        """Обработка команды /link_account для привязки аккаунта"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Если у пользователя уже есть email, значит аккаунт уже подключен
            if user.email:
                await message.answer(
                    "Ваш аккаунт Telegram уже привязан к аккаунту BotHub.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            try:
                # Генерируем реальную ссылку через usecase
                link = await account_connection_usecase.generate_connection_link(user)

                # Правильное экранирование специальных символов
                escaped_link = link.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]")

                # Отправляем сообщение с правильно отформатированной ссылкой
                message_text = f"Для привязки вашего Telegram к существующему аккаунту BotHub, перейдите по ссылке:\n\n[Привязать аккаунт]({escaped_link})\n\nПосле привязки вы сможете использовать ваши токены из аккаунта BotHub."

                await message.answer(
                    message_text,
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

                logger.info(f"Пользователь {user.id} запросил ссылку для привязки аккаунта")

            except Exception as link_error:
                logger.error(f"Ошибка при генерации ссылки: {link_error}", exc_info=True)
                await message.answer(
                    "Не удалось сгенерировать ссылку для привязки.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды link_account: {e}", exc_info=True)
            await message.answer(
                "Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )