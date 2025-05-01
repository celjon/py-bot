from typing import Optional, List, Dict, Any
from src.domain.entity.user import User
import json
import os
import aiosqlite


class UserRepository:
    """Репозиторий для работы с пользователями"""

    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        # Не вызываем асинхронный метод напрямую в конструкторе

    async def ensure_db_exists(self):
        """Проверяет существование БД и создает таблицы при необходимости"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id TEXT UNIQUE,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    language_code TEXT,
                    bothub_id TEXT,
                    bothub_access_token TEXT,
                    bothub_access_token_created_at TEXT,
                    registered_at TEXT,
                    current_chat_index INTEGER DEFAULT 1
                )
            """)
            await db.commit()

    async def find_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Поиск пользователя по Telegram ID"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()

            if row:
                return User(
                    id=row['id'],
                    telegram_id=row['telegram_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    language_code=row['language_code'],
                    bothub_id=row['bothub_id'],
                    bothub_access_token=row['bothub_access_token'],
                    registered_at=row['registered_at'],
                    current_chat_index=row['current_chat_index']
                )

            return None

    async def save(self, user: User) -> int:
        """Сохранение нового пользователя"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO users (
                    telegram_id, first_name, last_name, username, 
                    language_code, bothub_id, bothub_access_token, 
                    registered_at, current_chat_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.telegram_id,
                    user.first_name,
                    user.last_name,
                    user.username,
                    user.language_code,
                    user.bothub_id,
                    user.bothub_access_token,
                    user.registered_at.isoformat(),
                    user.current_chat_index
                )
            )
            await db.commit()
            return cursor.lastrowid

    async def update(self, user: User) -> None:
        """Обновление существующего пользователя"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users SET
                    first_name = ?,
                    last_name = ?,
                    username = ?,
                    language_code = ?,
                    bothub_id = ?,
                    bothub_access_token = ?,
                    current_chat_index = ?
                WHERE id = ?
                """,
                (
                    user.first_name,
                    user.last_name,
                    user.username,
                    user.language_code,
                    user.bothub_id,
                    user.bothub_access_token,
                    user.current_chat_index,
                    user.id
                )
            )
            await db.commit()

    async def find_all(self) -> List[User]:
        """Получение всех пользователей"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users")
            rows = await cursor.fetchall()

            return [
                User(
                    id=row['id'],
                    telegram_id=row['telegram_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    language_code=row['language_code'],
                    bothub_id=row['bothub_id'],
                    bothub_access_token=row['bothub_access_token'],
                    registered_at=row['registered_at'],
                    current_chat_index=row['current_chat_index']
                )
                for row in rows
            ]