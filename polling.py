
import asyncio
import logging
from src.config.settings import get_settings
from src.delivery.telegram.bot import create_bot
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция для запуска бота в режиме long polling"""
    logger.info("Starting bot in long polling mode...")

    # Получаем настройки
    settings = get_settings()

    # Инициализируем репозитории
    user_repository = UserRepository()
    chat_repository = ChatRepository()

    # Создаём бота и диспетчер с использованием репозиториев
    bot, dp = create_bot(settings, user_repository, chat_repository)

    # Логируем для отладки
    logger.info(f"Using custom Telegram API URL: {settings.TELEGRAM_API_URL}")
    logger.info("Bot started, polling for updates...")

    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}", exc_info=True)