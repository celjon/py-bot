import asyncpg
import logging
from typing import Optional, List
from datetime import datetime
from src.domain.entity.present import Present
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class PresentRepository:
    """Репозиторий для работы с подарками в PostgreSQL"""

    async def find_by_id(self, present_id: int) -> Optional[Present]:
        """Найти подарок по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM presents WHERE id = $1"
            row = await connection.fetchrow(query, present_id)

            if not row:
                return None

            return self._row_to_present(row)
        finally:
            await release_db_connection(connection)

    async def save(self, present: Present) -> int:
        """Сохранить подарок в базу данных"""
        connection = await get_db_connection()
        try:
            if present.id:
                # Обновляем существующий
                await self.update(present)
                return present.id
            else:
                # Создаем новый
                query = """
                    INSERT INTO presents (user_id, tokens, notified, parsed_at, notified_at)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """

                present_id = await connection.fetchval(
                    query,
                    present.user_id, present.tokens, present.notified,
                    present.parsed_at or datetime.now(), present.notified_at
                )

                present.id = present_id
                return present_id
        finally:
            await release_db_connection(connection)

    async def update(self, present: Present) -> None:
        """Обновить подарок в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE presents SET
                    user_id = $2, tokens = $3, notified = $4, parsed_at = $5, notified_at = $6
                WHERE id = $1
            """

            await connection.execute(
                query,
                present.id, present.user_id, present.tokens, present.notified,
                present.parsed_at, present.notified_at
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, present_id: int) -> bool:
        """Удалить подарок из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM presents WHERE id = $1"
            result = await connection.execute(query, present_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def find_by_user_id(self, user_id: int) -> List[Present]:
        """Найти подарки по user_id"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM presents WHERE user_id = $1 ORDER BY parsed_at DESC"
            rows = await connection.fetch(query, user_id)

            return [self._row_to_present(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_unnotified_by_user_id(self, user_id: int) -> List[Present]:
        """Найти неуведомленные подарки пользователя"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT * FROM presents 
                WHERE user_id = $1 AND notified = FALSE 
                ORDER BY parsed_at DESC
            """
            rows = await connection.fetch(query, user_id)

            return [self._row_to_present(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_all_unnotified(self) -> List[Present]:
        """Найти все неуведомленные подарки"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT * FROM presents 
                WHERE notified = FALSE 
                ORDER BY parsed_at DESC
            """
            rows = await connection.fetch(query)

            return [self._row_to_present(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def mark_notified(self, present_id: int) -> None:
        """Отметить подарок как уведомленный"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE presents 
                SET notified = TRUE, notified_at = $1
                WHERE id = $2
            """
            await connection.execute(query, datetime.now(), present_id)
        finally:
            await release_db_connection(connection)

    async def mark_user_presents_notified(self, user_id: int) -> int:
        """Отметить все подарки пользователя как уведомленные"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE presents 
                SET notified = TRUE, notified_at = $1
                WHERE user_id = $2 AND notified = FALSE
            """
            result = await connection.execute(query, datetime.now(), user_id)

            # Извлекаем количество обновленных записей
            updated_count = int(result.split()[-1]) if result else 0
            return updated_count
        finally:
            await release_db_connection(connection)

    async def get_total_tokens_by_user_id(self, user_id: int) -> int:
        """Получить общее количество токенов в подарках пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT COALESCE(SUM(tokens), 0) FROM presents WHERE user_id = $1"
            return await connection.fetchval(query, user_id)
        finally:
            await release_db_connection(connection)

    async def get_unnotified_tokens_by_user_id(self, user_id: int) -> int:
        """Получить количество токенов в неуведомленных подарках пользователя"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT COALESCE(SUM(tokens), 0) 
                FROM presents 
                WHERE user_id = $1 AND notified = FALSE
            """
            return await connection.fetchval(query, user_id)
        finally:
            await release_db_connection(connection)

    async def count_by_user_id(self, user_id: int) -> int:
        """Получить количество подарков пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM presents WHERE user_id = $1"
            return await connection.fetchval(query, user_id)
        finally:
            await release_db_connection(connection)

    async def count_unnotified_by_user_id(self, user_id: int) -> int:
        """Получить количество неуведомленных подарков пользователя"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM presents WHERE user_id = $1 AND notified = FALSE"
            return await connection.fetchval(query, user_id)
        finally:
            await release_db_connection(connection)

    async def get_total_count(self) -> int:
        """Получить общее количество подарков"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM presents"
            return await connection.fetchval(query)
        finally:
            await release_db_connection(connection)

    async def get_stats(self) -> dict:
        """Получить статистику подарков"""
        connection = await get_db_connection()
        try:
            # Общее количество
            total_count = await connection.fetchval("SELECT COUNT(*) FROM presents")

            # Неуведомленные
            unnotified_count = await connection.fetchval(
                "SELECT COUNT(*) FROM presents WHERE notified = FALSE"
            )

            # Общая сумма токенов
            total_tokens = await connection.fetchval(
                "SELECT COALESCE(SUM(tokens), 0) FROM presents"
            )

            # Сумма неуведомленных токенов
            unnotified_tokens = await connection.fetchval(
                "SELECT COALESCE(SUM(tokens), 0) FROM presents WHERE notified = FALSE"
            )

            # Количество пользователей с подарками
            users_with_presents = await connection.fetchval(
                "SELECT COUNT(DISTINCT user_id) FROM presents"
            )

            # Количество пользователей с неуведомленными подарками
            users_with_unnotified = await connection.fetchval(
                "SELECT COUNT(DISTINCT user_id) FROM presents WHERE notified = FALSE"
            )

            return {
                'total_count': total_count,
                'unnotified_count': unnotified_count,
                'total_tokens': total_tokens,
                'unnotified_tokens': unnotified_tokens,
                'users_with_presents': users_with_presents,
                'users_with_unnotified': users_with_unnotified
            }
        finally:
            await release_db_connection(connection)

    def _row_to_present(self, row) -> Present:
        """Преобразование строки из БД в объект Present"""
        return Present(
            id=row['id'],
            user_id=row['user_id'],
            tokens=row['tokens'],
            notified=row['notified'],
            parsed_at=row['parsed_at'],
            notified_at=row['notified_at']
        )