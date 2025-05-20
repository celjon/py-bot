# src/delivery/telegram/services/notification_service.py

import logging
from typing import Optional
from aiogram import Bot
from src.domain.entity.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений пользователям"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_account_connection_success(
        self,
        user: User,
        email: str,
        connection_type: str = "full_merge"
    ) -> bool:
        """
        Отправляет уведомление об успешном подключении аккаунта

        Args:
            user: Пользователь Telegram
            email: Email подключенного аккаунта
            connection_type: Тип подключения (full_merge или second_bot_connection)

        Returns:
            bool: True если уведомление отправлено успешно
        """
        if not user.telegram_id:
            logger.warning(f"У пользователя {user.id} нет telegram_id для отправки уведомления")
            return False

        try:
            if connection_type == "full_merge":
                message = (
                    "🎉 **Аккаунт успешно привязан!**\n\n"
                    f"Ваш Telegram теперь связан с аккаунтом BotHub:\n"
                    f"📧 **{email}**\n\n"
                    "Теперь вы можете использовать все возможности своего аккаунта через этого бота!\n\n"
                    "✨ Доступные функции:\n"
                    "• Общение с нейросетями\n"
                    "• Генерация изображений\n"
                    "• Веб-поиск\n"
                    "• И многое другое!\n\n"
                    "Начните с команды /start"
                )
            elif connection_type == "second_bot_connection":
                message = (
                    "🔗 **Python-бот подключен!**\n\n"
                    f"Python-бот успешно добавлен к вашему аккаунту:\n"
                    f"📧 **{email}**\n\n"
                    "Теперь вы можете использовать оба бота:\n"
                    "• Обычный Telegram-бот\n"
                    "• **Python-бот** (этот бот)\n\n"
                    "Ваши токены и подписка работают в обоих ботах.\n\n"
                    "Начните с команды /start"
                )
            else:
                # Общее сообщение для других типов
                message = (
                    "✅ **Аккаунт обновлен!**\n\n"
                    f"Ваш аккаунт успешно связан с:\n"
                    f"📧 **{email}**\n\n"
                    "Начните с команды /start"
                )

            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="Markdown"
            )

            logger.info(f"Уведомление о подключении аккаунта отправлено пользователю {user.id} (TG: {user.telegram_id})")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user.id}: {e}", exc_info=True)
            return False

    async def send_account_connection_error(
        self,
        user: User,
        error_message: str
    ) -> bool:
        """
        Отправляет уведомление об ошибке при подключении аккаунта

        Args:
            user: Пользователь Telegram
            error_message: Сообщение об ошибке

        Returns:
            bool: True если уведомление отправлено успешно
        """
        if not user.telegram_id:
            logger.warning(f"У пользователя {user.id} нет telegram_id для отправки уведомления об ошибке")
            return False

        try:
            message = (
                "❌ **Ошибка подключения аккаунта**\n\n"
                f"При подключении вашего аккаунта произошла ошибка:\n\n"
                f"**{error_message}**\n\n"
                "Попробуйте снова или обратитесь в поддержку, если проблема повторяется.\n\n"
                "Для повторной попытки используйте команду /link_account"
            )

            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="Markdown"
            )

            logger.info(f"Уведомление об ошибке отправлено пользователю {user.id} (TG: {user.telegram_id})")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об ошибке пользователю {user.id}: {e}", exc_info=True)
            return False

    async def send_generic_notification(
        self,
        user: User,
        title: str,
        message: str
    ) -> bool:
        """
        Отправляет общее уведомление пользователю

        Args:
            user: Пользователь Telegram
            title: Заголовок уведомления
            message: Текст сообщения

        Returns:
            bool: True если уведомление отправлено успешно
        """
        if not user.telegram_id:
            logger.warning(f"У пользователя {user.id} нет telegram_id для отправки уведомления")
            return False

        try:
            full_message = f"**{title}**\n\n{message}"

            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=full_message,
                parse_mode="Markdown"
            )

            logger.info(f"Уведомление '{title}' отправлено пользователю {user.id} (TG: {user.telegram_id})")
            return True

        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user.id}: {e}", exc_info=True)
            return False