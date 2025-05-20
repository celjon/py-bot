import asyncpg
import json
import logging
from typing import Optional, List, Dict, Any
from src.domain.entity.model import Model
from src.config.database import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class ModelRepository:
    """Репозиторий для работы с моделями в PostgreSQL"""

    async def find_by_id(self, model_id: str) -> Optional[Model]:
        """Найти модель по ID"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM models WHERE id = $1"
            row = await connection.fetchrow(query, model_id)

            if not row:
                return None

            return self._row_to_model(row)
        finally:
            await release_db_connection(connection)

    async def save(self, model: Model) -> None:
        """Сохранить модель в базу данных"""
        connection = await get_db_connection()
        try:
            # Проверяем, существует ли модель
            existing = await self.find_by_id(model.id)

            if existing:
                # Обновляем существующую
                await self.update(model)
            else:
                # Создаем новую
                query = """
                    INSERT INTO models (id, label, max_tokens, features)
                    VALUES ($1, $2, $3, $4)
                """

                # Сериализуем JSON поля
                features_json = json.dumps(model.features) if model.features else None

                await connection.execute(
                    query,
                    model.id, model.label, model.max_tokens, features_json
                )
        finally:
            await release_db_connection(connection)

    async def update(self, model: Model) -> None:
        """Обновить модель в базе данных"""
        connection = await get_db_connection()
        try:
            query = """
                UPDATE models SET
                    label = $2, max_tokens = $3, features = $4
                WHERE id = $1
            """

            # Сериализуем JSON поля
            features_json = json.dumps(model.features) if model.features else None

            await connection.execute(
                query,
                model.id, model.label, model.max_tokens, features_json
            )
        finally:
            await release_db_connection(connection)

    async def delete(self, model_id: str) -> bool:
        """Удалить модель из базы данных"""
        connection = await get_db_connection()
        try:
            query = "DELETE FROM models WHERE id = $1"
            result = await connection.execute(query, model_id)
            return result == "DELETE 1"
        finally:
            await release_db_connection(connection)

    async def get_all(self) -> List[Model]:
        """Получить все модели"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM models ORDER BY id"
            rows = await connection.fetch(query)

            return [self._row_to_model(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def find_by_feature(self, feature: str) -> List[Model]:
        """Найти модели с определенной функцией"""
        connection = await get_db_connection()
        try:
            query = "SELECT * FROM models WHERE features ? $1 ORDER BY id"
            rows = await connection.fetch(query, feature)

            return [self._row_to_model(row) for row in rows]
        finally:
            await release_db_connection(connection)

    async def get_text_models(self) -> List[Model]:
        """Получить текстовые модели"""
        return await self.find_by_feature("TEXT_TO_TEXT")

    async def get_image_generation_models(self) -> List[Model]:
        """Получить модели для генерации изображений"""
        return await self.find_by_feature("TEXT_TO_IMAGE")

    async def get_image_analysis_models(self) -> List[Model]:
        """Получить модели для анализа изображений"""
        return await self.find_by_feature("IMAGE_TO_TEXT")

    async def sync_models(self, models_data: List[Dict[str, Any]]) -> None:
        """Синхронизация моделей с данными из BotHub API"""
        connection = await get_db_connection()
        try:
            # Получаем существующие модели
            existing_models = set()
            existing_rows = await connection.fetch("SELECT id FROM models")
            for row in existing_rows:
                existing_models.add(row['id'])

            # Обновляем/создаем модели
            new_models = set()
            for model_data in models_data:
                model = Model(
                    id=model_data['id'],
                    label=model_data.get('label'),
                    max_tokens=model_data.get('max_tokens'),
                    features=model_data.get('features', [])
                )

                await self.save(model)
                new_models.add(model.id)

            # Удаляем модели, которых больше нет в API
            models_to_delete = existing_models - new_models
            for model_id in models_to_delete:
                await self.delete(model_id)
                logger.info(f"Удалена устаревшая модель: {model_id}")

            logger.info(f"Синхронизировано {len(new_models)} моделей")
        finally:
            await release_db_connection(connection)

    async def count(self) -> int:
        """Получить общее количество моделей"""
        connection = await get_db_connection()
        try:
            query = "SELECT COUNT(*) FROM models"
            return await connection.fetchval(query)
        finally:
            await release_db_connection(connection)

    def _row_to_model(self, row) -> Model:
        """Преобразование строки из БД в объект Model"""
        # Десериализуем JSON поля
        features = json.loads(row['features']) if row['features'] else []

        return Model(
            id=row['id'],
            label=row['label'],
            max_tokens=row['max_tokens'],
            features=features
        )