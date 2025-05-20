import os
from typing import Dict, Any
import asyncpg
from src.config.settings import get_settings


class DatabaseConfig:
    """Конфигурация подключения к базе данных"""

    def __init__(self):
        self.settings = get_settings()
        self._pool = None

    async def create_pool(self) -> asyncpg.Pool:
        """Создание пула подключений к PostgreSQL"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.settings.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
        return self._pool

    async def close_pool(self):
        """Закрытие пула подключений"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def get_connection(self):
        """Получение подключения из пула"""
        pool = await self.create_pool()
        return await pool.acquire()

    async def release_connection(self, connection):
        """Возврат подключения в пул"""
        pool = await self.create_pool()
        await pool.release(connection)


# Глобальный экземпляр конфигурации БД
db_config = DatabaseConfig()


async def get_db_connection():
    """Хелпер для получения подключения к БД"""
    return await db_config.get_connection()


async def release_db_connection(connection):
    """Хелпер для возврата подключения в пул"""
    await db_config.release_connection(connection)