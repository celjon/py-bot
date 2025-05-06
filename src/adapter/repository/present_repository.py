import aiosqlite
import logging
from typing import Optional, List
from datetime import datetime
from src.domain.entity.present import Present


logger = logging.getLogger(__name__)


class PresentRepository:
    """Репозиторий для работы с подарками токенов"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS presents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tokens INTEGER NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0,
                    parsed_at TEXT NOT NULL,
                    notified_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            await db.commit()

    async def save(self, present: Present) -> int:
        """Сохранить подарок токенов в базу данных"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO presents (
                    user_id, tokens, notified, parsed_at, notified_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                present.user_id,
                present.tokens,
                int(present.notified),
                present.parsed_at.isoformat(),
                present.notified_at.isoformat() if present.notified_at else None
            ))
            await db.commit()
            return cursor.lastrowid

    async def update(self, present: Present) -> None:
        """Обновить подарок токенов в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE presents SET
                    tokens = ?,
                    notified = ?,
                    parsed_at = ?,
                    notified_at = ?
                WHERE id = ?
            ''', (
                present.tokens,
                int(present.notified),
                present.parsed_at.isoformat(),
                present.notified_at.isoformat() if present.notified_at else None,
                present.id
            ))
            await db.commit()

    async def find_by_id(self, present_id: int) -> Optional[Present]:
        """Найти подарок токенов по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM presents WHERE id = ?",
                (present_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return Present(
                id=row['id'],
                user_id=row['user_id'],
                tokens=row['tokens'],
                notified=bool(row['notified']),
                parsed_at=datetime.fromisoformat(row['parsed_at']),
                notified_at=datetime.fromisoformat(row['notified_at']) if row['notified_at'] else None
            )

    async def find_by_user_id(self, user_id: int) -> List[Present]:
        """Найти все подарки токенов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM presents WHERE user_id = ? ORDER BY parsed_at DESC",
                (user_id,)
            )
            rows = await cursor.fetchall()

            presents = []
            for row in rows:
                presents.append(Present(
                    id=row['id'],
                    user_id=row['user_id'],
                    tokens=row['tokens'],
                    notified=bool(row['notified']),
                    parsed_at=datetime.fromisoformat(row['parsed_at']),
                    notified_at=datetime.fromisoformat(row['notified_at']) if row['notified_at'] else None
                ))

            return presents

    async def find_unnotified_by_user_id(self, user_id: int) -> List[Present]:
        """Найти все неуведомленные подарки токенов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM presents WHERE user_id = ? AND notified = 0 ORDER BY parsed_at",
                (user_id,)
            )
            rows = await cursor.fetchall()

            presents = []
            for row in rows:
                presents.append(Present(
                    id=row['id'],
                    user_id=row['user_id'],
                    tokens=row['tokens'],
                    notified=bool(row['notified']),
                    parsed_at=datetime.fromisoformat(row['parsed_at']),
                    notified_at=datetime.fromisoformat(row['notified_at']) if row['notified_at'] else None
                ))

            return presents
