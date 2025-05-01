from typing import Optional, List, Dict, Any
from src.domain.entity.chat import Chat
import json
import aiosqlite


class ChatRepository:
    """Репозиторий для работы с чатами"""

    def __init__(self, db_path: str = "chats.db"):
        self.db_path = db_path
        # Не вызываем асинхронный метод напрямую в конструкторе

    async def ensure_db_exists(self):
        """Проверяет существование БД и создает таблицы при необходимости"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_index INTEGER DEFAULT 1,
                    bothub_chat_id TEXT,
                    bothub_chat_model TEXT,
                    context_remember INTEGER DEFAULT 1,
                    context_counter INTEGER DEFAULT 0,
                    links_parse INTEGER DEFAULT 0,
                    formula_to_image INTEGER DEFAULT 0,
                    answer_to_voice INTEGER DEFAULT 0,
                    system_prompt TEXT DEFAULT '',
                    name TEXT,
                    buffer TEXT,
                    UNIQUE(user_id, chat_index)
                )
            """)
            await db.commit()

    async def find_by_user_id_and_chat_index(self, user_id: int, chat_index: int) -> Optional[Chat]:
        """Поиск чата по ID пользователя и индексу чата"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM chats WHERE user_id = ? AND chat_index = ?",
                (user_id, chat_index)
            )
            row = await cursor.fetchone()

            if row:
                # Преобразуем буфер из JSON в список словарей
                buffer = json.loads(row['buffer']) if row['buffer'] else None

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
                    system_prompt=row['system_prompt'],
                    name=row['name'],
                    buffer=buffer
                )

            return None

    async def save(self, chat: Chat) -> int:
        """Сохранение нового чата"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        # Проверим, существует ли уже чат с такой комбинацией user_id и chat_index
        existing_chat = await self.find_by_user_id_and_chat_index(chat.user_id, chat.chat_index)
        if existing_chat:
            # Если чат уже существует, обновим его и вернем его ID
            chat.id = existing_chat.id
            await self.update(chat)
            return existing_chat.id

        # Преобразуем буфер в JSON
        buffer_json = json.dumps(chat.buffer) if chat.buffer else None

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO chats (
                    user_id, chat_index, bothub_chat_id, bothub_chat_model,
                    context_remember, context_counter, links_parse,
                    formula_to_image, answer_to_voice, system_prompt,
                    name, buffer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat.user_id,
                    chat.chat_index,
                    chat.bothub_chat_id,
                    chat.bothub_chat_model,
                    int(chat.context_remember),
                    chat.context_counter,
                    int(chat.links_parse),
                    int(chat.formula_to_image),
                    int(chat.answer_to_voice),
                    chat.system_prompt,
                    chat.name,
                    buffer_json
                )
            )
            await db.commit()
            return cursor.lastrowid


    async def update(self, chat: Chat) -> None:
        """Обновление существующего чата"""
        # Сначала убедимся, что база данных существует
        await self.ensure_db_exists()

        # Преобразуем буфер в JSON
        buffer_json = json.dumps(chat.buffer) if chat.buffer else None

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE chats SET
                    bothub_chat_id = ?,
                    bothub_chat_model = ?,
                    context_remember = ?,
                    context_counter = ?,
                    links_parse = ?,
                    formula_to_image = ?,
                    answer_to_voice = ?,
                    system_prompt = ?,
                    name = ?,
                    buffer = ?
                WHERE id = ?
                """,
                (
                    chat.bothub_chat_id,
                    chat.bothub_chat_model,
                    int(chat.context_remember),
                    chat.context_counter,
                    int(chat.links_parse),
                    int(chat.formula_to_image),
                    int(chat.answer_to_voice),
                    chat.system_prompt,
                    chat.name,
                    buffer_json,
                    chat.id
                )
            )
            await db.commit()