# src/delivery/telegram/services/account_service.py
import logging
from typing import Tuple
from src.domain.entity.user import User
from src.domain.usecase.account_connection import AccountConnectionUseCase

logger = logging.getLogger(__name__)


class AccountService:
    """Сервис для работы с аккаунтами"""

    @staticmethod
    async def generate_connection_link(user: User, account_connection_usecase: AccountConnectionUseCase) -> Tuple[
        bool, str]:
        """
        Генерация ссылки для привязки аккаунта

        Returns:
            Tuple[bool, str]: (success, link_or_error_message)
        """
        try:
            # Если у пользователя уже есть email, значит аккаунт уже подключен
            if user.email:
                return False, "✅ Ваш аккаунт Telegram уже привязан к аккаунту BotHub."

            # Генерируем ссылку
            link = await account_connection_usecase.generate_connection_link(user)
            return True, link

        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка при генерации ссылки для пользователя {user.id}: {error_message}", exc_info=True)

            if "502 Bad Gateway" in error_message or "временно недоступен" in error_message:
                return False, "🔄 Сервер BotHub временно недоступен. Пожалуйста, попробуйте позже."
            elif "NOT_ENOUGH_TOKENS" in error_message:
                return False, "💎 Недостаточно токенов для выполнения операции."
            else:
                return False, f"❌ Не удалось сгенерировать ссылку для привязки."

    @staticmethod
    def format_connection_message(link: str) -> str:
        """
        Форматирование сообщения со ссылкой для привязки

        Args:
            link: Ссылка для привязки

        Returns:
            str: Отформатированное сообщение
        """
        # Используем простой формат без Markdown для ссылки
        message = (
            "🔗 Привязка аккаунта BotHub\n\n"
            "Для привязки вашего Telegram к существующему аккаунту BotHub, "
            "перейдите по ссылке:\n\n"
            f"{link}\n\n"
            "После привязки вы сможете использовать ваши токены из аккаунта BotHub.\n\n"
            "💡 Если у вас еще нет аккаунта BotHub, создайте его на bothub.chat"
        )

        return message