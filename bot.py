import asyncio
import logging
from telebot.async_telebot import AsyncTeleBot
from src.config.settings import get_settings
from src.delivery.telegram.bot import create_bot

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

    # Создаем бота
    bot = create_bot(settings)

    # Добавьте эти строки для исследования объекта бота
    logger.info(f"Bot attributes: {dir(bot)}")
    logger.info(
        f"Bot API URL attributes: {[attr for attr in dir(bot) if 'api' in attr.lower() or 'url' in attr.lower() or 'server' in attr.lower()]}")

    # Настраиваем URL Telegram Bot API для локального сервера
    if settings.TELEGRAM_API_URL:
        logger.info(f"Using custom Telegram API URL: {settings.TELEGRAM_API_URL}")
        try:
            # Попробуем разные способы установки API URL
            if hasattr(bot, 'api_url'):
                bot.api_url = settings.TELEGRAM_API_URL
            elif hasattr(bot, 'server'):
                bot.server = settings.TELEGRAM_API_URL
            else:
                logger.warning("Could not set custom API URL - no supported attribute found")
        except Exception as e:
            logger.warning(f"Could not set custom API URL: {e}")

    # Запускаем long polling
    logger.info("Bot started, polling for updates...")
    await bot.polling(non_stop=True, interval=0, timeout=60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}", exc_info=True)