from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any
import json
import logging

from src.config.settings import get_settings, Settings
from src.delivery.telegram.bot import create_bot

logger = logging.getLogger(__name__)


# Модель данных для вебхука Telegram
class TelegramUpdate(BaseModel):
    update_id: int
    message: Dict[str, Any] = None
    edited_message: Dict[str, Any] = None
    channel_post: Dict[str, Any] = None
    edited_channel_post: Dict[str, Any] = None
    callback_query: Dict[str, Any] = None


def create_app():
    """Фабричный метод для создания FastAPI приложения"""
    app = FastAPI(
        title="Telegram Bot API",
        description="API для взаимодействия с Telegram ботом",
        version="1.0.0",
    )

    # Инициализация бота
    settings = get_settings()
    bot = create_bot(settings)

    @app.post("/webhook")
    async def webhook(update: TelegramUpdate):
        """Обработчик вебхуков от Telegram"""
        try:
            # Преобразование Pydantic модели в dict и затем в JSON
            update_json = json.dumps(update.dict())

            # Обработка обновления ботом
            await bot.process_new_updates([update_json])

            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/health")
    async def health_check():
        """Проверка здоровья сервиса"""
        return {"status": "ok"}

    return app