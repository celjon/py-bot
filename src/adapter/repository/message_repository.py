import asyncpg
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from src.domain.entity.message import Message, MessageDirection, MessageType, MessageStatus
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class MessageRepository:
    """Репозиторий для работы с сообщениями в PostgreSQL"""

    async def find_by_id(self, message_id: int) -> Optional[Message]:
        """Найти сообщение по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM messages WHERE id = $1"
            row = await connection.fetchrow(query, message_id)

            if not row:
                return None

            return self._row_to_message(row)
        finally:
            await release_db_connection(connection)

    async def save(self, message: Message) -> int:
        """Сохранить сообщение в базу данных"""
        connection = await get_db_connection()
        try:
            query = """
                INSERT INTO messages (
                    user_id, chat_index, message_id, direction, type, status,
                    chat_id, text, data, sent_at, parsed_at, worker, related_message_id
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                ) RETURNING id
            """

            # Сериализуем JSON поля
            data_json = json.dumps(message.data) if message.data else None

            msg_id = await connection.fetchval(
                query,
                message.user_id, message.chat_index, message.message_id,
                message.direction.value, message.type.value, message.status.value,
                message.chat_id, message.text, data_json,
                message.sent_at or datetime.now(), message.parsed_at or datetime.now(),
                message.worker, message.related_message_id
            )

            message.id = msg_id
            return msg_id
        finally:
            await release_db_connection(connection)

    async def update(self, message: Message) -> None:
        """Обновить сообщение в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE messages SET
                    user_id = $2, chat_index = $3, message_id = $4, direction = $5,
                    type = $6, status = $7, chat_id = $8, text = $9, data = $10,
                    sent_at = $11, parsed_at = $12, worker = $13, related_message_id = $14
                WHERE id = $1
            """

            # Сериализуем JSON поля
            data_json = json.dumps(message.data) if message.data else None

            await connection.execute(
                query,
                message.id, message.user_id, message.chat_index, message.message_id,
                message.direction.value, message.type.value, message.status.value,
                message.chat_id, message.text, data_json,
                message.sent_at, message.parsed_at, message.worker, message.related_message_id
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, message_id: int) -> bool:
        """Удалить сообщение из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM messages WHERE id = $1"
            result = await connection.execute(query, message_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def find_by_user_id(self, user_id: int, limit: int = 100, offset: int = 0) -> List[Message]:
        """Найти сообщения по user_id"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT * FROM messages 
                WHERE user_id = $1 
                ORDER BY sent_at DESC 
                LIMIT $2 OFFSET $3
            """
            rows = await connection.fetch(query, user_id, limit, offset)

            return [self._row_to_message(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_by_chat_id(self, chat_id: int, limit: int = 100, offset: int = 0) -> List[Message]:
        """Найти сообщения по chat_id"""
        connection = await get_db_connection()
        try:
            query = """
                SELECT * FROM messages 
                WHERE chat_id = $1 
                ORDER BY sent_at DESC 
                LIMIT $2 OFFSET $3
            """
            rows = await connection.fetch(query, chat_id, limit, offset)

            return [self._row_to_message(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_unprocessed_messages(self, worker_id: Optional[int] = None, limit: int = 10) -> List[Message]:
        """Найти необработанные сообщения"""
        connection = await get_db_connection()
        try:
            if worker_id is not None:
                # Ищем сообщения для конкретного воркера
                query = """
                    SELECT * FROM messages 
                    WHERE (status = $1 OR (status = $2 AND worker = $3))
                    ORDER BY sent_at
                    LIMIT $4
                """
                rows = await connection.fetch(
                    query,
                    MessageStatus.NOT_PROCESSED.value,
                    MessageStatus.PROCESSING.value,
                    worker_id,
                    limit
                )
            else:
                # Ищем любые необработанные сообщения
                query = """
                    SELECT * FROM messages 
                    WHERE status = $1 
                    ORDER BY sent_at
                    LIMIT $2
                """
                rows = await connection.fetch(query, MessageStatus.NOT_PROCESSED.value, limit)

            return [self._row_to_message(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def assign_to_worker(self, message_id: int, worker_id: int) -> bool:
        """Назначить сообщение воркеру"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE messages 
                SET status = $1, worker = $2, parsed_at = $3
                WHERE id = $4 AND status = $5
            """
            result = await connection.execute(
                query,
                MessageStatus.PROCESSING.value,
                worker_id,
                datetime.now(),
                message_id,
                MessageStatus.NOT_PROCESSED.value
            )
            return result == "UPDATE 1"
        finally:
            await release_db_connection(connection)

    async def mark_processed(self, message_id: int) -> None:
        """Отметить сообщение как обработанное"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE messages 
                SET status = $1, parsed_at = $2
                WHERE id = $3
            """
            await connection.execute(
                query,
                MessageStatus.PROCESSED.value,
                datetime.now(),
                message_id
            )
        finally:
            await release_db_connection(connection)

    async def mark_error(self, message_id: int) -> None:
        """Отметить сообщение как ошибочное"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE messages 
                SET status = $1, parsed_at = $2
                WHERE id = $3
            """
            await connection.execute(
                query,
                MessageStatus.ERROR.value,
                datetime.now(),
                message_id
            )
        finally:
            await release_db_connection(connection)

    async def cleanup_old_messages(self, days: int = 30) -> int:
        """Очистить старые сообщения (старше указанного количества дней)"""
        connection = await get_db_connection()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = "DELETE FROM messages WHERE sent_at < $1"
            result = await connection.execute(query, cutoff_date)

            # Извлекаем количество удаленных записей из результата
            deleted_count = int(result.split()[-1]) if result else 0
            return deleted_count
        finally:
            await release_db_connection(connection)

    async def get_message_stats(self) -> Dict[str, int]:
        """Получить статистику сообщений"""
        connection = await get_db_connection()
        try:
            # Общее количество
            total = await connection.fetchval("SELECT COUNT(*) FROM messages")

            # По статусам
            unprocessed = await connection.fetchval(
                "SELECT COUNT(*) FROM messages WHERE status = $1",
                MessageStatus.NOT_PROCESSED.value
            )

            processing = await connection.fetchval(
                "SELECT COUNT(*) FROM messages WHERE status = $1",
                MessageStatus.PROCESSING.value
            )

            processed = await connection.fetchval(
                "SELECT COUNT(*) FROM messages WHERE status = $1",
                MessageStatus.PROCESSED.value
            )

            error = await connection.fetchval(
                "SELECT COUNT(*) FROM messages WHERE status = $1",
                MessageStatus.ERROR.value
            )

            # За последние 24 часа
            last_24h = await connection.fetchval(
                "SELECT COUNT(*) FROM messages WHERE sent_at > $1",
                datetime.now() - timedelta(hours=24)
            )

            return {
                'total': total,
                'unprocessed': unprocessed,
                'processing': processing,
                'processed': processed,
                'error': error,
                'last_24h': last_24h
            }
        finally:
            await release_db_connection(connection)

    async def find_stuck_messages(self, timeout_minutes: int = 30) -> List[Message]:
        """Найти зависшие сообщения (в статусе PROCESSING слишком долго)"""
        connection = await get_db_connection()
        try:
            cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
            query = """
                SELECT * FROM messages 
                WHERE status = $1 AND parsed_at < $2
                ORDER BY parsed_at
            """
            rows = await connection.fetch(query, MessageStatus.PROCESSING.value, cutoff_time)

            return [self._row_to_message(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def reset_stuck_messages(self, timeout_minutes: int = 30) -> int:
        """Сбросить зависшие сообщения в статус NOT_PROCESSED"""
        connection = await get_db_connection()
        try:
            cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
            query = """
                UPDATE messages 
                SET status = $1, worker = NULL, parsed_at = $2
                WHERE status = $3 AND parsed_at < $4
            """
            result = await connection.execute(
                query,
                MessageStatus.NOT_PROCESSED.value,
                datetime.now(),
                MessageStatus.PROCESSING.value,
                cutoff_time
            )

            # Извлекаем количество обновленных записей
            reset_count = int(result.split()[-1]) if result else 0
            return reset_count
        finally:
            await release_db_connection(connection)

    def _row_to_message(self, row) -> Message:
        """Преобразование строки из БД в объект Message"""
        # Десериализуем JSON поля
        data = json.loads(row['data']) if row['data'] else {}

        return Message(
            id=row['id'],
            user_id=row['user_id'],
            chat_index=row['chat_index'],
            message_id=row['message_id'],
            direction=MessageDirection(row['direction']),
            type=MessageType(row['type']),
            status=MessageStatus(row['status']),
            chat_id=row['chat_id'],
            text=row['text'],
            data=data,
            sent_at=row['sent_at'],
            parsed_at=row['parsed_at'],
            worker=row['worker'],
            related_message_id=row['related_message_id']
        )