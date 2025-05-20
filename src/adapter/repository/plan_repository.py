import asyncpg
import logging
from typing import Optional, List, Dict, Any
from src.domain.entity.plan import Plan
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class PlanRepository:
    """Репозиторий для работы с планами в PostgreSQL"""

    async def find_by_id(self, plan_id: int) -> Optional[Plan]:
        """Найти план по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans WHERE id = $1"
            row = await connection.fetchrow(query, plan_id)

            if not row:
                return None

            return self._row_to_plan(row)
        finally:
            await release_db_connection(connection)

    async def find_by_bothub_id(self, bothub_id: str) -> Optional[Plan]:
        """Найти план по BotHub ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans WHERE bothub_id = $1"
            row = await connection.fetchrow(query, bothub_id)

            if not row:
                return None

            return self._row_to_plan(row)
        finally:
            await release_db_connection(connection)

    async def save(self, plan: Plan) -> int:
        """Сохранить план в базу данных"""
        connection = await get_db_connection()
        try:
            if plan.id:
                # Обновляем существующий
                await self.update(plan)
                return plan.id
            else:
                # Создаем новый
                query = """
                    INSERT INTO plans (bothub_id, type, price, currency, tokens)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """

                plan_id = await connection.fetchval(
                    query,
                    plan.bothub_id, plan.type, plan.price, plan.currency, plan.tokens
                )

                plan.id = plan_id
                return plan_id
        finally:
            await release_db_connection(connection)

    async def update(self, plan: Plan) -> None:
        """Обновить план в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE plans SET
                    bothub_id = $2, type = $3, price = $4, currency = $5, tokens = $6
                WHERE id = $1
            """

            await connection.execute(
                query,
                plan.id, plan.bothub_id, plan.type, plan.price, plan.currency, plan.tokens
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, plan_id: int) -> bool:
        """Удалить план из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM plans WHERE id = $1"
            result = await connection.execute(query, plan_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def get_all(self) -> List[Plan]:
        """Получить все планы"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans ORDER BY price ASC NULLS FIRST"
            rows = await connection.fetch(query)

            return [self._row_to_plan(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_by_type(self, plan_type: str) -> List[Plan]:
        """Найти планы по типу"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans WHERE type = $1 ORDER BY price ASC NULLS FIRST"
            rows = await connection.fetch(query, plan_type)

            return [self._row_to_plan(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def sync_plans(self, plans_data: List[Dict[str, Any]]) -> None:
        """Синхронизация планов с данными из BotHub API"""
        connection = await get_db_connection()
        try:
            # Получаем существующие планы
            existing_plans = {}
            existing_rows = await connection.fetch("SELECT * FROM plans")
            for row in existing_rows:
                existing_plans[row['bothub_id']] = self._row_to_plan(row)

            # Обновляем/создаем планы
            synced_bothub_ids = set()
            for plan_data in plans_data:
                bothub_id = plan_data.get('id') or plan_data.get('bothub_id')
                if not bothub_id:
                    continue

                plan = Plan(
                    bothub_id=bothub_id,
                    type=plan_data.get('type'),
                    price=plan_data.get('price'),
                    currency=plan_data.get('currency'),
                    tokens=plan_data.get('tokens')
                )

                # Если план уже существует, обновляем его ID
                if bothub_id in existing_plans:
                    plan.id = existing_plans[bothub_id].id

                await self.save(plan)
                synced_bothub_ids.add(bothub_id)

            # Удаляем планы, которых больше нет в API
            for bothub_id, existing_plan in existing_plans.items():
                if bothub_id not in synced_bothub_ids:
                    await self.delete(existing_plan.id)
                    logger.info(f"Удален устаревший план: {bothub_id}")

            logger.info(f"Синхронизировано {len(synced_bothub_ids)} планов")
        finally:
            await release_db_connection(connection)

    async def count(self) -> int:
        """Получить общее количество планов"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM plans"
            return await connection.fetchval(query)
        finally:
            await release_db_connection(connection)

    async def get_free_plans(self) -> List[Plan]:
        """Получить бесплатные планы"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans WHERE price = 0 OR price IS NULL ORDER BY tokens DESC NULLS LAST"
            rows = await connection.fetch(query)

            return [self._row_to_plan(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def get_paid_plans(self) -> List[Plan]:
        """Получить платные планы"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM plans WHERE price > 0 ORDER BY price ASC"
            rows = await connection.fetch(query)

            return [self._row_to_plan(row) for row in rows]
        finally:
            await release_db_connection(connection)

    def _row_to_plan(self, row) -> Plan:
        """Преобразование строки из БД в объект Plan"""
        return Plan(
            id=row['id'],
            bothub_id=row['bothub_id'],
            type=row['type'],
            price=row['price'],
            currency=row['currency'],
            tokens=row['tokens']
        )