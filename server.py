import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import json
from datetime import datetime

from src.config.settings import get_settings, Settings
from src.config.database import get_db_path  # Добавим импорт
from src.adapter.repository.user_repository import UserRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Используем единый путь к БД
DB_PATH = get_db_path()

app = FastAPI(title="BotHub WebHook Server",
              description="API для обработки вебхуков от BotHub",
              version="1.0.0")

async def get_user_repository():
    """Получение репозитория пользователей"""
    repository = UserRepository(DB_PATH)
    return repository


@app.post("/bothub-webhook")
async def bothub_webhook(
        request: Request,
        settings: Settings = Depends(get_settings),
        user_repository: UserRepository = Depends(get_user_repository)
):
    """Обработчик вебхуков от BotHub"""
    try:
        # Логируем все заголовки для отладки
        logger.info(f"Получен вебхук. Заголовки: {dict(request.headers)}")

        # Проверяем секретный ключ
        bot_secret_key = request.headers.get("botsecretkey")
        logger.info(f"Secret key from header: {bot_secret_key}")
        logger.info(f"Expected secret key: {settings.BOTHUB_SECRET_KEY}")

        if not bot_secret_key or bot_secret_key != settings.BOTHUB_SECRET_KEY:
            logger.error(f"Неверный секретный ключ вебхука: {bot_secret_key}")
            return JSONResponse(
                status_code=403,
                content={"error": "Недействительный секретный ключ"}
            )

        # Получаем данные вебхука
        try:
            body = await request.body()
            text = body.decode('utf-8')
            logger.info(f"Raw webhook body: {text}")

            if not text:
                logger.error("Пустое тело запроса")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука (пустое тело)"}
                )

            data = json.loads(text)
            logger.info(f"Parsed webhook data: {data}")
        except Exception as e:
            logger.error(f"Ошибка при парсинге JSON: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Некорректные данные вебхука: {str(e)}"}
            )

        # Проверяем тип вебхука
        if not data.get("type"):
            logger.error(f"Отсутствует тип вебхука: {data}")
            return JSONResponse(
                status_code=400,
                content={"error": "Некорректные данные вебхука (отсутствует тип)"}
            )

        logger.info(f"Получен вебхук типа: {data['type']}")

        # Обрабатываем разные типы вебхуков
        if data["type"] == "merge":
            # Проверяем, что это вебхук для Python-бота
            if not data.get("pythonBot"):
                logger.info("Получен вебхук merge для PHP-бота, игнорируем")
                return {"status": "ignored - php bot"}

            logger.info("Обрабатываем merge для Python-бота")

            # Обработка привязки аккаунта
            if not data.get("oldId") or not data.get("newId") or "email" not in data:
                logger.error(f"Некорректные данные для типа 'merge': {data}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука для типа 'merge'"}
                )

            # Находим пользователя по старому ID
            user = await user_repository.find_by_bothub_id(data["oldId"])
            if not user:
                logger.error(f"Пользователь с bothub_id={data['oldId']} не найден")
                return JSONResponse(
                    status_code=404,
                    content={"error": "Пользователь не найден"}
                )

            logger.info(f"Найден пользователь {user.id} для merge")

            # Обновляем данные пользователя
            user.bothub_id = data["newId"]
            user.email = data["email"]
            user.bothub_access_token = None
            user.state = None

            # Сохраняем изменения
            await user_repository.update(user)

            logger.info(f"Аккаунт пользователя {user.id} успешно привязан к аккаунту {data['email']}")

            # Отправляем уведомление пользователю (если возможно)
            # TODO: Добавить отправку уведомления через бота

            return {"status": "success"}

        # Другие типы вебхуков
        else:
            logger.warning(f"Неизвестный тип вебхука: {data['type']}")
            return {"status": "unknown_type"}

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука BotHub: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        )


# Добавим эндпоинт для проверки работы ngrok
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/test-webhook")
async def test_webhook():
    """Тестовый эндпоинт для проверки доступности"""
    return {"message": "Webhook server is running", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)