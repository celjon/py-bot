import asyncio
import os
import logging
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'bothub.db')


async def init_db():
    """Инициализация базы данных"""
    # Создаем директорию для базы данных, если она не существует
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    logger.info(f"Initializing database at {DB_PATH}")

    # Инициализация репозиториев
    user_repository = UserRepository(DB_PATH)
    chat_repository = ChatRepository(DB_PATH)

    # Создание таблиц
    await user_repository.init_db()
    await chat_repository.init_db()

    logger.info("Database initialized successfully")


if __name__ == "__main__":
    asyncio.run(init_db())