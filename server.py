import os
import uvicorn
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import json
from datetime import datetime

from src.config.settings import get_settings, Settings
from src.config.database import get_db_path
from src.adapter.repository.user_repository import UserRepository
from src.lib.bot_instance import get_bot_instance, is_bot_available
from src.delivery.telegram.services.notification_service import NotificationService

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

        # Проверяем тип вебхука - ожидаем только "merge"
        if data.get("type") != "merge":
            logger.error(f"Неожиданный тип вебхука: {data.get('type')}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Неподдерживаемый тип вебхука: {data.get('type')}"}
            )

        # Проверяем обязательные поля
        required_fields = ["oldId", "newId", "email"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            logger.error(f"Отсутствуют обязательные поля: {missing_fields}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Отсутствуют поля: {missing_fields}"}
            )

        old_user_id = data["oldId"]  # ID Telegram пользователя (удаляется)
        new_user_id = data["newId"]  # ID основного пользователя (остается)
        email = data["email"]
        is_python_bot = data.get("pythonBot", False)

        logger.info(
            f"Обрабатываем merge: oldId={old_user_id}, newId={new_user_id}, email={email}, pythonBot={is_python_bot}")

        # Находим пользователя Telegram-бота по старому ID
        telegram_user = await user_repository.find_by_bothub_id(old_user_id)

        if not telegram_user:
            logger.error(f"Telegram пользователь с bothub_id={old_user_id} не найден")
            return JSONResponse(
                status_code=404,
                content={"error": "Telegram пользователь не найден"}
            )

        logger.info(f"Найден Telegram пользователь {telegram_user.id} (TG: {telegram_user.telegram_id})")

        # Обновляем данные Telegram пользователя после merge
        telegram_user.bothub_id = new_user_id  # Новый ID от основного аккаунта
        telegram_user.email = email  # Email от основного аккаунта
        telegram_user.bothub_access_token = None  # Сбрасываем токен для получения нового

        # Сохраняем изменения
        await user_repository.update(telegram_user)

        logger.info(
            f"Merge завершен: telegram_user.id={telegram_user.id} получил bothub_id={new_user_id}, email={email}")

        # Отправляем уведомление пользователю о успешной привязке
        if is_bot_available():
            bot = get_bot_instance()
            notification_service = NotificationService(bot)

            # Определяем тип подключения для уведомления
            connection_type = "python_bot" if is_python_bot else "regular_bot"

            await notification_service.send_account_connection_success(
                telegram_user,
                email,
                connection_type
            )
        else:
            logger.warning("Бот недоступен для отправки уведомления")

        return {
            "status": "success",
            "message": "Account successfully connected",
            "pythonBot": is_python_bot
        }

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка сервера: {str(e)}"}
        )


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)