import asyncpg
import json
import logging
from typing import Optional, List, Dict, Any
from src.domain.entity.chat import Chat
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class ChatRepository:
    """Репозиторий для работы с чатами пользователей в PostgreSQL"""

    async def find_by_id(self, chat_id: int) -> Optional[Chat]:
        """Найти чат по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users_chats WHERE id = $1"
            row = await connection.fetchrow(query, chat_id)

            if not row:
                return None

            return self._row_to_user_chat(row)
        finally:
            await release_db_connection(connection)

    async def find_by_user_id_and_chat_index(self, user_id: int, chat_index: int) -> Optional[Chat]:
        """Найти чат по user_id и chat_index"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users_chats WHERE user_id = $1 AND chat_index = $2"
            row = await connection.fetchrow(query, user_id, chat_index)

            if not row:
                return None

            return self._row_to_user_chat(row)
        finally:
            await release_db_connection(connection)

    async def find_by_bothub_chat_id(self, bothub_chat_id: str) -> Optional[Chat]:
        """Найти чат по BotHub chat ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users_chats WHERE bothub_chat_id = $1"
            row = await connection.fetchrow(query, bothub_chat_id)

            if not row:
                return None

            return self._row_to_user_chat(row)
        finally:
            await release_db_connection(connection)

    async def find_by_user_id(self, user_id: int) -> List[Chat]:
        """Найти все чаты пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users_chats WHERE user_id = $1 ORDER BY chat_index"
            rows = await connection.fetch(query, user_id)

            return [self._row_to_user_chat(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def save(self, user_chat: Chat) -> int:
        """Сохранить чат в базу данных"""
        connection = await get_db_connection()
        try:
            # Проверяем, существует ли уже такой чат
            existing = await self.find_by_user_id_and_chat_index(user_chat.user_id, user_chat.chat_index)

            if existing:
                # Обновляем существующий
                user_chat.id = existing.id
                await self.update(user_chat)
                return existing.id
            else:
                # Создаем новый
                query = """
                    INSERT INTO users_chats (
                        user_id, chat_index, bothub_chat_id, bothub_chat_model,
                        context_remember, context_counter, links_parse, buffer,
                        system_prompt, formula_to_image, answer_to_voice, name
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                    ) RETURNING id
                """

                # Сериализуем JSON поля
                buffer_json = json.dumps(user_chat.buffer) if user_chat.buffer else None

                chat_id = await connection.fetchval(
                    query,
                    user_chat.user_id, user_chat.chat_index, user_chat.bothub_chat_id, user_chat.bothub_chat_model,
                    user_chat.context_remember, user_chat.context_counter, user_chat.links_parse, buffer_json,
                    user_chat.system_prompt, user_chat.formula_to_image, user_chat.answer_to_voice, user_chat.name
                )

                user_chat.id = chat_id
                return chat_id
        finally:
            await release_db_connection(connection)

    async def update(self, user_chat: Chat) -> None:
        """Обновить чат в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE users_chats SET
                    bothub_chat_id = $2, bothub_chat_model = $3, context_remember = $4,
                    context_counter = $5, links_parse = $6, buffer = $7, system_prompt = $8,
                    formula_to_image = $9, answer_to_voice = $10, name = $11
                WHERE id = $1
            """

            # Сериализуем JSON поля
            buffer_json = json.dumps(user_chat.buffer) if user_chat.buffer else None

            await connection.execute(
                query,
                user_chat.id, user_chat.bothub_chat_id, user_chat.bothub_chat_model, user_chat.context_remember,
                user_chat.context_counter, user_chat.links_parse, buffer_json, user_chat.system_prompt,
                user_chat.formula_to_image, user_chat.answer_to_voice, user_chat.name
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, chat_id: int) -> bool:
        """Удалить чат из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM users_chats WHERE id = $1"
            result = await connection.execute(query, chat_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def get_paginated_chats(self, user_id: int, page: int, items_per_page: int) -> List[Chat]:
        """Получить постранично чаты пользователя"""
        connection = await get_db_connection()
        try:
            if page == 1:
                # Первая страница - стандартные чаты (1-5)
                query = """
                    SELECT * FROM users_chats 
                    WHERE user_id = $1 AND chat_index <= 5 
                    ORDER BY chat_index
                """
                rows = await connection.fetch(query, user_id)
            else:
                # Остальные страницы - пользовательские чаты
                offset = (page - 1) * items_per_page - 5
                query = """
                    SELECT * FROM users_chats 
                    WHERE user_id = $1 AND chat_index > 5 
                    ORDER BY chat_index 
                    LIMIT $2 OFFSET $3
                """
                rows = await connection.fetch(query, user_id, items_per_page, offset)

            return [self._row_to_user_chat(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def get_total_pages(self, user_id: int, items_per_page: int) -> int:
        """Получить общее количество страниц для чатов пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM users_chats WHERE user_id = $1 AND chat_index > 5"
            count = await connection.fetchval(query, user_id)

            # Рассчитываем количество страниц для пользовательских чатов
            custom_pages = (count + items_per_page - 1) // items_per_page

            # Добавляем первую страницу с стандартными чатами
            return custom_pages + 1
        finally:
            await release_db_connection(connection)

    async def get_last_chat_index(self, user_id: int) -> int:
        """Получить последний индекс чата для пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT MAX(chat_index) FROM users_chats WHERE user_id = $1"
            max_index = await connection.fetchval(query, user_id)

            # Если нет чатов, возвращаем 5 (последний стандартный чат)
            return max(5, max_index or 5)
        finally:
            await release_db_connection(connection)

    async def count_by_user_id(self, user_id: int) -> int:
        """Получить количество чатов пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM users_chats WHERE user_id = $1"
            return await connection.fetchval(query, user_id)
        finally:
            await release_db_connection(connection)

    def _row_to_user_chat(self, row) -> Chat:
        """Преобразование строки из БД в объект UserChat"""
        # Десериализуем JSON поля
        buffer = json.loads(row['buffer']) if row['buffer'] else {}

        return Chat(
            id=row['id'],
            user_id=row['user_id'],
            chat_index=row['chat_index'],
            bothub_chat_id=row['bothub_chat_id'],
            bothub_chat_model=row['bothub_chat_model'],
            context_remember=row['context_remember'],
            context_counter=row['context_counter'],
            links_parse=row['links_parse'],
            buffer=buffer,
            system_prompt=row['system_prompt'],
            formula_to_image=row['formula_to_image'],
            answer_to_voice=row['answer_to_voice'],
            name=row['name']
        )