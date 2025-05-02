# Дополнение файла src/adapter/repository/user_repository.py

import aiosqlite
import json
import logging
from typing import Optional, List
from datetime import datetime
from src.domain.entity.user import User

logger = logging.getLogger(__name__)

class UserRepository:
    """Репозиторий для работы с пользователями в базе данных SQLite"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id TEXT UNIQUE,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    language_code TEXT,
                    bothub_id TEXT,
                    bothub_group_id TEXT,
                    bothub_access_token TEXT,
                    bothub_access_token_created_at TEXT,
                    current_chat_index INTEGER NOT NULL DEFAULT 1,
                    current_chat_list_page INTEGER NOT NULL DEFAULT 1,
                    gpt_model TEXT,
                    image_generation_model TEXT,
                    formula_to_image INTEGER NOT NULL DEFAULT 0,
                    links_parse INTEGER NOT NULL DEFAULT 0,
                    context_remember INTEGER NOT NULL DEFAULT 1,
                    answer_to_voice INTEGER NOT NULL DEFAULT 0,
                    state TEXT,
                    present_data TEXT,
                    referral_code TEXT,
                    buffer TEXT,
                    system_messages_to_delete TEXT,
                    registered_at TEXT NOT NULL
                )
            ''')
            await db.commit()

    async def find_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Найти пользователя по telegram_id"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Десериализуем JSON поля
            buffer = json.loads(row['buffer']) if row['buffer'] else {}
            system_messages_to_delete = json.loads(row['system_messages_to_delete']) if row['system_messages_to_delete'] else []

            # Десериализуем datetime
            bothub_access_token_created_at = datetime.fromisoformat(row['bothub_access_token_created_at']) if row['bothub_access_token_created_at'] else None

            return User(
                id=row['id'],
                telegram_id=row['telegram_id'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                username=row['username'],
                language_code=row['language_code'],
                bothub_id=row['bothub_id'],
                bothub_group_id=row['bothub_group_id'],
                bothub_access_token=row['bothub_access_token'],
                bothub_access_token_created_at=bothub_access_token_created_at,
                current_chat_index=row['current_chat_index'],
                current_chat_list_page=row['current_chat_list_page'],
                gpt_model=row['gpt_model'],
                image_generation_model=row['image_generation_model'],
                formula_to_image=bool(row['formula_to_image']),
                links_parse=bool(row['links_parse']),
                context_remember=bool(row['context_remember']),
                answer_to_voice=bool(row['answer_to_voice']),
                state=row['state'],
                present_data=row['present_data'],
                referral_code=row['referral_code'],
                buffer=buffer,
                system_messages_to_delete=system_messages_to_delete
            )

    async def find_by_username(self, username: str) -> Optional[User]:
        """Найти пользователя по username"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Десериализуем JSON поля
            buffer = json.loads(row['buffer']) if row['buffer'] else {}
            system_messages_to_delete = json.loads(row['system_messages_to_delete']) if row['system_messages_to_delete'] else []

            # Десериализуем datetime
            bothub_access_token_created_at = datetime.fromisoformat(row['bothub_access_token_created_at']) if row['bothub_access_token_created_at'] else None

            return User(
                id=row['id'],
                telegram_id=row['telegram_id'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                username=row['username'],
                language_code=row['language_code'],
                bothub_id=row['bothub_id'],
                bothub_group_id=row['bothub_group_id'],
                bothub_access_token=row['bothub_access_token'],
                bothub_access_token_created_at=bothub_access_token_created_at,
                current_chat_index=row['current_chat_index'],
                current_chat_list_page=row['current_chat_list_page'],
                gpt_model=row['gpt_model'],
                image_generation_model=row['image_generation_model'],
                formula_to_image=bool(row['formula_to_image']),
                links_parse=bool(row['links_parse']),
                context_remember=bool(row['context_remember']),
                answer_to_voice=bool(row['answer_to_voice']),
                state=row['state'],
                present_data=row['present_data'],
                referral_code=row['referral_code'],
                buffer=buffer,
                system_messages_to_delete=system_messages_to_delete
            )

    async def save(self, user: User) -> int:
        """Сохранить пользователя в базу данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сериализуем JSON поля
            buffer = json.dumps(user.buffer) if user.buffer else None
            system_messages_to_delete = json.dumps(user.system_messages_to_delete) if user.system_messages_to_delete else None

            # Сериализуем datetime
            bothub_access_token_created_at = user.bothub_access_token_created_at.isoformat() if user.bothub_access_token_created_at else None

            cursor = await db.execute('''
                INSERT INTO users (
                    telegram_id, first_name, last_name, username, language_code,
                    bothub_id, bothub_group_id, bothub_access_token, bothub_access_token_created_at,
                    current_chat_index, current_chat_list_page, gpt_model, image_generation_model,
                    formula_to_image, links_parse, context_remember, answer_to_voice,
                    state, present_data, referral_code, buffer, system_messages_to_delete,
                    registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.telegram_id, user.first_name, user.last_name, user.username, user.language_code,
                user.bothub_id, user.bothub_group_id, user.bothub_access_token, bothub_access_token_created_at,
                user.current_chat_index, user.current_chat_list_page, user.gpt_model, user.image_generation_model,
                int(user.formula_to_image), int(user.links_parse), int(user.context_remember),
                int(user.answer_to_voice),
                user.state, user.present_data, user.referral_code, buffer, system_messages_to_delete,
                datetime.now().isoformat()
            ))
            await db.commit()
            return cursor.lastrowid

    async def update(self, user: User) -> None:
        """Обновить пользователя в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сериализуем JSON поля
            buffer = json.dumps(user.buffer) if user.buffer else None
            system_messages_to_delete = json.dumps(user.system_messages_to_delete) if user.system_messages_to_delete else None

            # Сериализуем datetime
            bothub_access_token_created_at = user.bothub_access_token_created_at.isoformat() if user.bothub_access_token_created_at else None

            await db.execute('''
                UPDATE users SET
                    first_name = ?,
                    last_name = ?,
                    username = ?,
                    language_code = ?,
                    bothub_id = ?,
                    bothub_group_id = ?,
                    bothub_access_token = ?,
                    bothub_access_token_created_at = ?,
                    current_chat_index = ?,
                    current_chat_list_page = ?,
                    gpt_model = ?,
                    image_generation_model = ?,
                    formula_to_image = ?,
                    links_parse = ?,
                    context_remember = ?,
                    answer_to_voice = ?,
                    state = ?,
                    present_data = ?,
                    referral_code = ?,
                    buffer = ?,
                    system_messages_to_delete = ?
                WHERE id = ?
            ''', (
                user.first_name, user.last_name, user.username, user.language_code,
                user.bothub_id, user.bothub_group_id, user.bothub_access_token, bothub_access_token_created_at,
                user.current_chat_index, user.current_chat_list_page, user.gpt_model, user.image_generation_model,
                int(user.formula_to_image), int(user.links_parse), int(user.context_remember),
                int(user.answer_to_voice),
                user.state, user.present_data, user.referral_code, buffer, system_messages_to_delete,
                user.id
            ))
            await db.commit()

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Получить всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = await cursor.fetchall()

            users = []
            for row in rows:
                # Сериализуем JSON поля
                buffer = json.loads(row['buffer']) if row['buffer'] else {}
                system_messages_to_delete = json.loads(row['system_messages_to_delete']) if row['system_messages_to_delete'] else []

                # Сериализуем datetime
                bothub_access_token_created_at = datetime.fromisoformat(row['bothub_access_token_created_at']) if row['bothub_access_token_created_at'] else None

                users.append(User(
                    id=row['id'],
                    telegram_id=row['telegram_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    username=row['username'],
                    language_code=row['language_code'],
                    bothub_id=row['bothub_id'],
                    bothub_group_id=row['bothub_group_id'],
                    bothub_access_token=row['bothub_access_token'],
                    bothub_access_token_created_at=bothub_access_token_created_at,
                    current_chat_index=row['current_chat_index'],
                    current_chat_list_page=row['current_chat_list_page'],
                    gpt_model=row['gpt_model'],
                    image_generation_model=row['image_generation_model'],
                    formula_to_image=bool(row['formula_to_image']),
                    links_parse=bool(row['links_parse']),
                    context_remember=bool(row['context_remember']),
                    answer_to_voice=bool(row['answer_to_voice']),
                    state=row['state'],
                    present_data=row['present_data'],
                    referral_code=row['referral_code'],
                    buffer=buffer,
                    system_messages_to_delete=system_messages_to_delete
                ))

            return users