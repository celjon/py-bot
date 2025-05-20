import asyncpg
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.domain.entity.user import User
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class UserRepository:
    """Репозиторий для работы с пользователями в PostgreSQL"""

    async def find_by_id(self, user_id: int) -> Optional[User]:
        """Найти пользователя по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users WHERE id = $1"
            row = await connection.fetchrow(query, user_id)

            if not row:
                return None

            return self._row_to_user(row)
        finally:
            await release_db_connection(connection)

    async def find_by_tg_id(self, tg_id: str) -> Optional[User]:
        """Найти пользователя по Telegram ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users WHERE tg_id = $1"
            row = await connection.fetchrow(query, tg_id)

            if not row:
                return None

            return self._row_to_user(row)
        finally:
            await release_db_connection(connection)

    async def find_by_bothub_id(self, bothub_id: str) -> Optional[User]:
        """Найти пользователя по BotHub ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users WHERE bothub_id = $1"
            row = await connection.fetchrow(query, bothub_id)

            if not row:
                return None

            return self._row_to_user(row)
        finally:
            await release_db_connection(connection)

    async def find_by_username(self, username: str) -> Optional[User]:
        """Найти пользователя по username"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users WHERE username = $1"
            row = await connection.fetchrow(query, username)

            if not row:
                return None

            return self._row_to_user(row)
        finally:
            await release_db_connection(connection)

    async def save(self, user: User) -> int:
        """Сохранить пользователя в базу данных"""
        connection = await get_db_connection()
        try:
            query = """
                INSERT INTO users (
                    tg_id, first_name, last_name, username, email, language_code,
                    bothub_id, bothub_group_id, bothub_access_token, bothub_access_token_created_at,
                    state, gpt_model, image_generation_model, tool, present_data,
                    current_chat_index, system_messages_to_delete, referral_code,
                    current_chat_list_page, registered_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
                ) RETURNING id
            """

            # Сериализуем JSON поля
            system_messages_json = json.dumps(
                user.system_messages_to_delete) if user.system_messages_to_delete else None

            user_id = await connection.fetchval(
                query,
                user.tg_id, user.first_name, user.last_name, user.username, user.email, user.language_code,
                user.bothub_id, user.bothub_group_id, user.bothub_access_token, user.bothub_access_token_created_at,
                user.state, user.gpt_model, user.image_generation_model, user.tool, user.present_data,
                user.current_chat_index, system_messages_json, user.referral_code,
                user.current_chat_list_page, user.registered_at or datetime.now()
            )

            user.id = user_id
            return user_id
        finally:
            await release_db_connection(connection)

    async def update(self, user: User) -> None:
        """Обновить пользователя в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE users SET
                    tg_id = $2, first_name = $3, last_name = $4, username = $5, email = $6,
                    language_code = $7, bothub_id = $8, bothub_group_id = $9,
                    bothub_access_token = $10, bothub_access_token_created_at = $11,
                    state = $12, gpt_model = $13, image_generation_model = $14, tool = $15,
                    present_data = $16, current_chat_index = $17, system_messages_to_delete = $18,
                    referral_code = $19, current_chat_list_page = $20
                WHERE id = $1
            """

            # Сериализуем JSON поля
            system_messages_json = json.dumps(
                user.system_messages_to_delete) if user.system_messages_to_delete else None

            await connection.execute(
                query,
                user.id, user.tg_id, user.first_name, user.last_name, user.username, user.email,
                user.language_code, user.bothub_id, user.bothub_group_id,
                user.bothub_access_token, user.bothub_access_token_created_at,
                user.state, user.gpt_model, user.image_generation_model, user.tool,
                user.present_data, user.current_chat_index, system_messages_json,
                user.referral_code, user.current_chat_list_page
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, user_id: int) -> bool:
        """Удалить пользователя из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM users WHERE id = $1"
            result = await connection.execute(query, user_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Получить всех пользователей с пагинацией"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM users ORDER BY id LIMIT $1 OFFSET $2"
            rows = await connection.fetch(query, limit, offset)

            return [self._row_to_user(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def count(self) -> int:
        """Получить общее количество пользователей"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM users"
            return await connection.fetchval(query)
        finally:
            await release_db_connection(connection)

    async def find_users_with_presents(self) -> List[User]:
        """Найти пользователей с неуведомленными подарками"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT DISTINCT u.* FROM users u
                JOIN presents p ON u.id = p.user_id
                WHERE p.notified = FALSE
                ORDER BY u.id
            """
            rows = await connection.fetch(query)

            return [self._row_to_user(row) for row in rows]
        finally:
            await release_db_connection(connection)

    def _row_to_user(self, row) -> User:
        """Преобразование строки из БД в объект User"""
        # Десериализуем JSON поля
        system_messages = json.loads(row['system_messages_to_delete']) if row['system_messages_to_delete'] else []

        return User(
            id=row['id'],
            tg_id=row['tg_id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            username=row['username'],
            email=row['email'],
            language_code=row['language_code'],
            bothub_id=row['bothub_id'],
            bothub_group_id=row['bothub_group_id'],
            bothub_access_token=row['bothub_access_token'],
            bothub_access_token_created_at=row['bothub_access_token_created_at'],
            state=row['state'],
            gpt_model=row['gpt_model'],
            image_generation_model=row['image_generation_model'],
            tool=row['tool'],
            present_data=row['present_data'],
            current_chat_index=row['current_chat_index'],
            system_messages_to_delete=system_messages,
            referral_code=row['referral_code'],
            current_chat_list_page=row['current_chat_list_page'],
            registered_at=row['registered_at']
        )