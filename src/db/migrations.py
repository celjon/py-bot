import asyncio
import asyncpg
import logging
from typing import Dict, Any
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Миграции для создания PostgreSQL схемы аналогичной PHP боту"""

    def __init__(self):
        self.settings = get_settings()
        self.connection = None

    async def connect(self):
        """Подключение к PostgreSQL"""
        try:
            # Парсим DATABASE_URL из настроек
            db_url = self.settings.DATABASE_URL
            self.connection = await asyncpg.connect(db_url)
            logger.info("Подключение к PostgreSQL установлено")
        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise

    async def disconnect(self):
        """Закрытие подключения"""
        if self.connection:
            await self.connection.close()
            logger.info("Подключение к PostgreSQL закрыто")

    async def create_users_table(self):
        """Создание таблицы users"""
        query = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tg_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            email TEXT,
            language_code CHAR(2),
            bothub_id TEXT UNIQUE,
            bothub_group_id TEXT,
            registered_at TIMESTAMP DEFAULT NOW(),
            bothub_access_token TEXT,
            bothub_access_token_created_at TIMESTAMP,
            state SMALLINT,
            gpt_model TEXT,
            image_generation_model TEXT,
            tool TEXT,
            present_data TEXT,
            current_chat_index SMALLINT DEFAULT 1,
            system_messages_to_delete JSON,
            referral_code TEXT,
            current_chat_list_page INTEGER DEFAULT 1
        );

        -- Индексы для оптимизации
        CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id);
        CREATE INDEX IF NOT EXISTS idx_users_bothub_id ON users(bothub_id);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """
        await self.connection.execute(query)
        logger.info("Таблица users создана")

    async def create_users_chats_table(self):
        """Создание таблицы users_chats"""
        query = """
        CREATE TABLE IF NOT EXISTS users_chats (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chat_index SMALLINT DEFAULT 1,
            bothub_chat_id TEXT,
            bothub_chat_model TEXT,
            context_remember BOOLEAN DEFAULT TRUE,
            context_counter INTEGER DEFAULT 0,
            links_parse BOOLEAN DEFAULT FALSE,
            buffer JSON,
            system_prompt TEXT DEFAULT '',
            formula_to_image BOOLEAN DEFAULT FALSE,
            answer_to_voice BOOLEAN DEFAULT FALSE,
            name TEXT,
            UNIQUE(user_id, chat_index)
        );

        -- Индексы
        CREATE INDEX IF NOT EXISTS idx_users_chats_user_id ON users_chats(user_id);
        CREATE INDEX IF NOT EXISTS idx_users_chats_bothub_chat_id ON users_chats(bothub_chat_id);
        """
        await self.connection.execute(query)
        logger.info("Таблица users_chats создана")

    async def create_messages_table(self):
        """Создание таблицы messages"""
        query = """
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chat_index SMALLINT DEFAULT 1,
            message_id BIGINT,
            direction SMALLINT, -- 0=request, 1=response
            type SMALLINT, -- various message types
            status SMALLINT, -- 0=not_processed, 1=processed
            chat_id BIGINT,
            text TEXT,
            data JSON,
            sent_at TIMESTAMP DEFAULT NOW(),
            parsed_at TIMESTAMP DEFAULT NOW(),
            worker SMALLINT,
            related_message_id INTEGER REFERENCES messages(id)
        );

        -- Индексы для оптимизации
        CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
        CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
        CREATE INDEX IF NOT EXISTS idx_messages_worker ON messages(worker);
        CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
        """
        await self.connection.execute(query)
        logger.info("Таблица messages создана")

    async def create_models_table(self):
        """Создание таблицы models"""
        query = """
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            label TEXT,
            max_tokens INTEGER,
            features JSON
        );

        CREATE INDEX IF NOT EXISTS idx_models_label ON models(label);
        """
        await self.connection.execute(query)
        logger.info("Таблица models создана")

    async def create_plans_table(self):
        """Создание таблицы plans"""
        query = """
        CREATE TABLE IF NOT EXISTS plans (
            id SERIAL PRIMARY KEY,
            bothub_id TEXT,
            type TEXT,
            price DOUBLE PRECISION,
            currency TEXT,
            tokens INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_plans_bothub_id ON plans(bothub_id);
        CREATE INDEX IF NOT EXISTS idx_plans_type ON plans(type);
        """
        await self.connection.execute(query)
        logger.info("Таблица plans создана")

    async def create_presents_table(self):
        """Создание таблицы presents"""
        query = """
        CREATE TABLE IF NOT EXISTS presents (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tokens BIGINT,
            notified BOOLEAN DEFAULT FALSE,
            parsed_at TIMESTAMP DEFAULT NOW(),
            notified_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_presents_user_id ON presents(user_id);
        CREATE INDEX IF NOT EXISTS idx_presents_notified ON presents(notified);
        """
        await self.connection.execute(query)
        logger.info("Таблица presents создана")

    async def run_migrations(self):
        """Запуск всех миграций"""
        try:
            await self.connect()

            # Создаем таблицы в правильном порядке (с учетом внешних ключей)
            await self.create_users_table()
            await self.create_users_chats_table()
            await self.create_messages_table()
            await self.create_models_table()
            await self.create_plans_table()
            await self.create_presents_table()

            logger.info("Все миграции выполнены успешно")

        except Exception as e:
            logger.error(f"Ошибка при выполнении миграций: {e}")
            raise
        finally:
            await self.disconnect()

    async def rollback_migrations(self):
        """Откат миграций (удаление таблиц)"""
        try:
            await self.connect()

            # Удаляем таблицы в обратном порядке
            tables = ['presents', 'plans', 'models', 'messages', 'users_chats', 'users']

            for table in tables:
                await self.connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                logger.info(f"Таблица {table} удалена")

            logger.info("Все таблицы удалены")

        except Exception as e:
            logger.error(f"Ошибка при откате миграций: {e}")
            raise
        finally:
            await self.disconnect()


# Скрипт для запуска миграций
async def main():
    """Основная функция для запуска миграций"""
    import sys

    migration = DatabaseMigration()

    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        print("Выполняю откат миграций...")
        await migration.rollback_migrations()
        print("Откат завершен")
    else:
        print("Выполняю миграции...")
        await migration.run_migrations()
        print("Миграции завершены")


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())