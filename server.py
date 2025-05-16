import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import json
from datetime import datetime

from src.config.settings import get_settings, Settings
from src.adapter.repository.user_repository import UserRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bothub.db')

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
        # Проверяем секретный ключ
        bot_secret_key = request.headers.get("botsecretkey")
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
            if not text:
                logger.error("Пустое тело запроса")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука (пустое тело)"}
                )

            data = json.loads(text)
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

            # Обновляем данные пользователя
            user.bothub_id = data["newId"]
            user.email = data["email"]
            user.bothub_access_token = None
            user.state = None

            # Сохраняем изменения
            await user_repository.update(user)

            logger.info(f"Аккаунт пользователя {user.id} успешно привязан к аккаунту {data['email']}")
            return {"status": "success"}

        # Другие типы вебхуков
        elif data["type"] == "message":
            # Просто логируем получение вебхука типа 'message' 
            # Полная имплементация требует больше кода
            logger.info(f"Получен вебхук типа 'message'")
            return {"status": "success"}

        elif data["type"] == "present":
            # Просто логируем получение вебхука типа 'present'
            # Полная имплементация требует больше кода
            logger.info(f"Получен вебхук типа 'present'")
            return {"status": "success"}

        elif data["type"] == "presentViaEmail":
            # Просто логируем получение вебхука типа 'presentViaEmail'
            # Полная имплементация требует больше кода
            logger.info(f"Получен вебхук типа 'presentViaEmail'")
            return {"status": "success"}

        else:
            logger.warning(f"Неизвестный тип вебхука: {data['type']}")
            return {"status": "success"}

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука BotHub: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        )


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)