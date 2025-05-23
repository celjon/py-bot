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
                return False, (
                    "✅ **Ваш аккаунт уже привязан!**\n\n"
                    f"Email: **{user.email}**\n\n"
                    "Вы можете использовать все функции бота с вашим подключенным аккаунтом.\n\n"
                    "📝 Доступные команды:\n"
                    "• `/start` - главное меню\n"
                    "• `/gpt_config` - настройка моделей\n"
                    "• `/reset` - сброс контекста\n\n"
                    "🎯 Попробуйте просто написать сообщение для общения с ИИ!"
                )

            # Генерируем ссылку
            link = await account_connection_usecase.generate_connection_link(user)

            # ВАЖНО: После генерации ссылки нужно сохранить обновленного пользователя
            from src.adapter.repository.user_repository import UserRepository
            user_repo = UserRepository()
            await user_repo.update(user)
            logger.info(f"Пользователь {user.id} обновлен с новым bothub_id: {user.bothub_id}")

            return True, link

        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка при генерации ссылки для пользователя {user.id}: {error_message}", exc_info=True)

            if "502 Bad Gateway" in error_message or "временно недоступен" in error_message:
                return False, (
                    "🔄 **Сервер временно недоступен**\n\n"
                    "Попробуйте позже. Мы работаем над решением проблемы.\n\n"
                    "⏰ Обычно это занимает несколько минут."
                )
            elif "NOT_ENOUGH_TOKENS" in error_message:
                return False, (
                    "💎 **Недостаточно токенов**\n\n"
                    "Для выполнения операции требуются токены.\n\n"
                    "🔗 Попробуйте привязать аккаунт с активной подпиской."
                )
            else:
                return False, (
                    "❌ **Не удалось создать ссылку для привязки**\n\n"
                    "Возможные причины:\n"
                    "• Временные проблемы с сервером\n"
                    "• Проблемы с подключением\n\n"
                    "🔄 Попробуйте еще раз через несколько минут."
                )

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
            "🔗 **Привязка аккаунта BotHub**\n\n"
            "Для привязки вашего Telegram к существующему аккаунту BotHub, "
            "перейдите по ссылке:\n\n"
            f"👉 {link}\n\n"
            "📋 **Что произойдет после привязки:**\n"
            "• Доступ к вашим токенам и подписке\n"
            "• Синхронизация настроек\n"
            "• Полный функционал бота\n\n"
            "💡 **Нет аккаунта BotHub?**\n"
            "Создайте его на bothub.chat\n\n"
            "⚡ **Важно:** Ссылка действительна в течение нескольких минут"
        )

        return message