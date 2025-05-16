from src.domain.entity.user import User
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.config.settings import Settings
import logging

logger = logging.getLogger(__name__)


class AccountConnectionUseCase:
    """Юзкейс для подключения аккаунта"""

    def __init__(self, gateway: BothubGateway, settings: Settings):
        self.gateway = gateway
        self.settings = settings

    async def generate_connection_link(self, user: User) -> str:
        """
        Генерация ссылки для подключения Telegram к существующему аккаунту BotHub

        Args:
            user: Пользователь

        Returns:
            str: Ссылка для подключения
        """
        logger.info(f"Генерация ссылки для подключения аккаунта для пользователя {user.id}")
        try:
            return await self.gateway.generate_telegram_connection_link(user, self.settings)
        except Exception as e:
            logger.error(f"Ошибка при генерации ссылки: {str(e)}")
            error_message = str(e)

            if "502 Bad Gateway" in error_message or "Сервер BotHub временно недоступен" in error_message:
                raise Exception("Сервер BotHub временно недоступен. Пожалуйста, попробуйте позже.")
            else:
                raise Exception(f"Ошибка при генерации ссылки: {error_message}")