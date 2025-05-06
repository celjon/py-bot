# src/adapter/repository/chat_repository.py

import aiosqlite
import json
from typing import Optional, List
from src.domain.entity.chat import Chat


class ChatRepository:
    """Репозиторий для работы с чатами в базе данных SQLite"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_index INTEGER NOT NULL,
                    bothub_chat_id TEXT,
                    bothub_chat_model TEXT,
                    context_remember INTEGER NOT NULL DEFAULT 1,
                    context_counter INTEGER NOT NULL DEFAULT 0,
                    links_parse INTEGER NOT NULL DEFAULT 0,
                    formula_to_image INTEGER NOT NULL DEFAULT 0,
                    answer_to_voice INTEGER NOT NULL DEFAULT 0,
                    name TEXT,
                    system_prompt TEXT NOT NULL DEFAULT '',
                    buffer TEXT,
                    UNIQUE(user_id, chat_index)
                )
            ''')
            await db.commit()

    async def find_by_user_id_and_chat_index(self, user_id: int, chat_index: int) -> Optional[Chat]:
        """Найти чат по user_id и chat_index"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM chats WHERE user_id = ? AND chat_index = ?",
                (user_id, chat_index)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Сериализуем JSON поля
            buffer = json.loads(row['buffer']) if row['buffer'] else {}

            return Chat(
                id=row['id'],
                user_id=row['user_id'],
                chat_index=row['chat_index'],
                bothub_chat_id=row['bothub_chat_id'],
                bothub_chat_model=row['bothub_chat_model'],
                context_remember=bool(row['context_remember']),
                context_counter=row['context_counter'],
                links_parse=bool(row['links_parse']),
                formula_to_image=bool(row['formula_to_image']),
                answer_to_voice=bool(row['answer_to_voice']),
                name=row['name'],
                system_prompt=row['system_prompt'],
                buffer=buffer
            )

    async def save(self, chat: Chat) -> int:
        """Сохранить чат в базу данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сериализуем JSON поля
            buffer = json.dumps(chat.buffer) if chat.buffer else None

            cursor = await db.execute('''
                INSERT INTO chats (
                    user_id, chat_index, bothub_chat_id, bothub_chat_model,
                    context_remember, context_counter, links_parse, formula_to_image,
                    answer_to_voice, name, system_prompt, buffer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chat.user_id, chat.chat_index, chat.bothub_chat_id, chat.bothub_chat_model,
                int(chat.context_remember), chat.context_counter, int(chat.links_parse), int(chat.formula_to_image),
                int(chat.answer_to_voice), chat.name, chat.system_prompt, buffer
            ))
            await db.commit()
            return cursor.lastrowid

    async def update(self, chat: Chat) -> None:
        """Обновить чат в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сериализуем JSON поля
            buffer = json.dumps(chat.buffer) if chat.buffer else None

            await db.execute('''
                UPDATE chats SET
                    bothub_chat_id = ?,
                    bothub_chat_model = ?,
                    context_remember = ?,
                    context_counter = ?,
                    links_parse = ?,
                    formula_to_image = ?,
                    answer_to_voice = ?,
                    name = ?,
                    system_prompt = ?,
                    buffer = ?
                WHERE id = ?
            ''', (
                chat.bothub_chat_id, chat.bothub_chat_model,
                int(chat.context_remember), chat.context_counter, int(chat.links_parse), int(chat.formula_to_image),
                int(chat.answer_to_voice), chat.name, chat.system_prompt, buffer,
                chat.id
            ))
            await db.commit()

    async def get_paginated_chats(self, user_id: int, page: int, items_per_page: int) -> List[Chat]:
        """Получить постранично чаты пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Если это первая страница, вернуть default чаты (1-5)
            if page == 1:
                cursor = await db.execute(
                    "SELECT * FROM chats WHERE user_id = ? AND chat_index <= 5 ORDER BY chat_index",
                    (user_id,)
                )
            else:
                offset = (page - 1) * items_per_page - 5  # -5 потому что первые 5 на первой странице
                cursor = await db.execute(
                    "SELECT * FROM chats WHERE user_id = ? AND chat_index > 5 ORDER BY chat_index LIMIT ? OFFSET ?",
                    (user_id, items_per_page, offset)
                )

            rows = await cursor.fetchall()

            chats = []
            for row in rows:
                # Сериализуем JSON поля
                buffer = json.loads(row['buffer']) if row['buffer'] else {}

                chats.append(Chat(
                    id=row['id'],
                    user_id=row['user_id'],
                    chat_index=row['chat_index'],
                    bothub_chat_id=row['bothub_chat_id'],
                    bothub_chat_model=row['bothub_chat_model'],
                    context_remember=bool(row['context_remember']),
                    context_counter=row['context_counter'],
                    links_parse=bool(row['links_parse']),
                    formula_to_image=bool(row['formula_to_image']),
                    answer_to_voice=bool(row['answer_to_voice']),
                    name=row['name'],
                    system_prompt=row['system_prompt'],
                    buffer=buffer
                ))

            return chats

    async def get_total_pages(self, user_id: int, items_per_page: int) -> int:
        """Получить общее количество страниц для чатов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем количество чатов с индексом > 5
            cursor = await db.execute(
                "SELECT COUNT(*) FROM chats WHERE user_id = ? AND chat_index > 5",
                (user_id,)
            )
            count = await cursor.fetchone()
            count = count[0] if count else 0

            # Делим на количество элементов на странице и округляем вверх
            custom_pages = (count + items_per_page - 1) // items_per_page

            # Добавляем первую страницу с дефолтными чатами
            return custom_pages + 1

    async def get_last_chat_index(self, user_id: int) -> int:
        """Получить последний индекс чата для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT MAX(chat_index) FROM chats WHERE user_id = ?",
                (user_id,)
            )
            max_index = await cursor.fetchone()

            # Если нет чатов, вернуть 5 (последний стандартный чат)
            if not max_index or not max_index[0]:
                return 5

            # Иначе вернуть максимальный индекс
            return max(5, max_index[0])