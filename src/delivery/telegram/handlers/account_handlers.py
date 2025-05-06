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
                # Демо-версия: просто показываем сообщение
                # В полной версии будет:
                # link = await account_connection_usecase.generate_connection_link(user)

                link = "https://example.com/link_demo"  # Демо-ссылка

                # Отправляем сообщение с ссылкой
                await message.answer(
                    f"Для привязки вашего Telegram к существующему аккаунту BotHub, перейдите по ссылке:\n\n{link}\n\n"
                    f"После привязки вы сможете использовать ваши токены из аккаунта BotHub.",
                    reply_markup=get_main_keyboard(user, chat)
                )

                logger.info(f"Пользователь {user.id} запросил ссылку для привязки аккаунта")

            except Exception as link_error:
                logger.error(f"Ошибка при генерации ссылки: {link_error}", exc_info=True)
                await message.answer(
                    f"Не удалось сгенерировать ссылку для привязки. \n\n"
                    f"Вы можете вручную привязать аккаунт:\n"
                    f"1) Войдите в аккаунт на сайте bothub.chat\n"
                    f"2) Перейдите в настройки профиля\n"
                    f"3) Найдите раздел 'Подключенные аккаунты'\n"
                    f"4) Добавьте Telegram и следуйте инструкциям",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды link_account: {e}", exc_info=True)
            await message.answer(
                "Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )