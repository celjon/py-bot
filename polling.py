import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from src.config.settings import get_settings
from src.config.database import get_db_path  # Добавим импорт
from src.delivery.telegram.bot import create_bot
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Используем единый путь к БД
DB_PATH = get_db_path()

async def init_db():
    """Инициализация базы данных"""
    logger.info(f"Initializing database at {DB_PATH}")

    # Инициализация репозиториев
    user_repository = UserRepository(DB_PATH)
    chat_repository = ChatRepository(DB_PATH)

    # Создание таблиц
    await user_repository.init_db()
    await chat_repository.init_db()

    logger.info("Database initialized successfully")

    return user_repository, chat_repository


async def main():
    """Основная функция для запуска бота в режиме long polling"""
    logger.info("Starting bot in long polling mode...")

    # Получаем настройки
    settings = get_settings()

    # Инициализируем базу данных
    user_repository, chat_repository = await init_db()

    # Создаём бота и диспетчер с использованием реальных репозиториев
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