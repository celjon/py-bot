import asyncio
import logging
from src.db.migrations import DatabaseMigration
from src.config.settings import get_settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_database():
    """Инициализация базы данных PostgreSQL"""
    logger.info("Запуск инициализации базы данных...")

    # Проверяем настройки
    settings = get_settings()
    logger.info(f"Подключение к базе данных: {settings.DATABASE_URL}")

    # Запускаем миграции
    migration = DatabaseMigration()
    await migration.run_migrations()

    logger.info("Инициализация базы данных завершена")


async def rollback_database():
    """Откат базы данных (удаление всех таблиц)"""
    logger.warning("Запуск отката базы данных...")

    # Запускаем откат миграций
    migration = DatabaseMigration()
    await migration.rollback_migrations()

    logger.warning("Откат базы данных завершен")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "rollback":
            asyncio.run(rollback_database())
        elif sys.argv[1] == "init":
            asyncio.run(init_database())
        else:
            print("Использование: python init_db.py [init|rollback]")
            print("  init     - создать/обновить таблицы базы данных")
            print("  rollback - удалить все таблицы базы данных")
    else:
        # По умолчанию выполняем инициализацию
        asyncio.run(init_database())