import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json
from datetime import datetime

from src.config.settings import get_settings
from src.config.database import get_db_path
from src.adapter.repository.user_repository import UserRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
settings = get_settings()
DB_PATH = get_db_path()
app = FastAPI(title="BotHub WebHook Server", version="1.0.0")


@app.post("/bothub-webhook")
async def bothub_webhook(request: Request):
    """Обработчик вебхуков от BotHub"""
    try:
        # Проверяем секретный ключ
        bot_secret_key = request.headers.get("botsecretkey")
        if not bot_secret_key or bot_secret_key != settings.BOTHUB_SECRET_KEY:
            logger.error(f"Неверный секретный ключ: {bot_secret_key}")
            return JSONResponse(status_code=403, content={"error": "Недействительный ключ"})

        # Получаем данные
        try:
            body = await request.body()
            data = json.loads(body.decode('utf-8'))
            logger.info(f"Webhook data: {data}")
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return JSONResponse(status_code=400, content={"error": "Некорректные данные"})

        # Обрабатываем только тип "merge"
        if data.get("type") != "merge":
            logger.error(f"Неподдерживаемый тип: {data.get('type')}")
            return JSONResponse(status_code=400, content={"error": "Неподдерживаемый тип"})

        # Проверяем обязательные поля
        required_fields = ["oldId", "newId", "email"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Отсутствуют поля: {missing_fields}")
            return JSONResponse(status_code=400, content={"error": f"Отсутствуют поля: {missing_fields}"})

        old_user_id = data["oldId"]
        new_user_id = data["newId"]
        email = data["email"]

        logger.info(f"Merge: {old_user_id} -> {new_user_id} ({email})")

        # Обновляем пользователя
        user_repository = UserRepository(DB_PATH)
        telegram_user = await user_repository.find_by_bothub_id(old_user_id)

        if not telegram_user:
            logger.error(f"Пользователь с bothub_id={old_user_id} не найден")
            return JSONResponse(status_code=404, content={"error": "Пользователь не найден"})

        # Обновляем данные
        telegram_user.bothub_id = new_user_id
        telegram_user.email = email
        telegram_user.bothub_access_token = None  # Сбрасываем токен

        await user_repository.update(telegram_user)

        logger.info(f"Аккаунт {telegram_user.id} успешно привязан к {email}")

        return {"status": "success", "message": "Account connected"}

    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка: {str(e)}"}
        )


@app.get("/health")
async def health_check():
    """Проверка здоровья"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    # Получаем порт из переменной окружения
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)