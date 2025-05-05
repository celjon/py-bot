from fastapi import APIRouter, Request, HTTPException, Depends
from src.config.settings import get_settings, Settings
from src.adapter.repository.user_repository import UserRepository
from typing import Dict, Any
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/bothub-webhook")
async def bothub_webhook(
        request: Request,
        settings: Settings = Depends(get_settings),
        user_repository: UserRepository = Depends(lambda: UserRepository(DB_PATH))
):
    """Обработчик вебхуков от BotHub"""
    try:
        # Проверяем секретный ключ
        bot_secret_key = request.headers.get("botsecretkey")
        if not bot_secret_key or bot_secret_key != settings.BOTHUB_WEBHOOK_SECRET_KEY:
            logger.error(f"Неверный секретный ключ вебхука: {bot_secret_key}")
            raise HTTPException(status_code=403, detail="Недействительный секретный ключ")

        # Получаем данные вебхука
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Ошибка при парсинге JSON: {str(e)}")
            raise HTTPException(status_code=400, detail="Некорректные данные вебхука")

        # Проверяем тип вебхука
        if not data.get("type"):
            logger.error(f"Отсутствует тип вебхука: {data}")
            raise HTTPException(status_code=400, detail="Некорректные данные вебхука")

        logger.info(f"Получен вебхук типа: {data['type']}")

        # Обрабатываем разные типы вебхуков
        if data["type"] == "merge":
            # Обработка привязки аккаунта
            if not data.get("oldId") or not data.get("newId") or not "email" in data:
                logger.error(f"Некорректные данные для типа 'merge': {data}")
                raise HTTPException(status_code=400, detail="Некорректные данные вебхука")

            # Находим пользователя по старому ID
            user = await user_repository.find_by_bothub_id(data["oldId"])
            if not user:
                logger.error(f"Пользователь с bothub_id={data['oldId']} не найден")
                raise HTTPException(status_code=404, detail="Пользователь не найден")

            # Обновляем данные пользователя
            user.bothub_id = data["newId"]
            user.email = data["email"]
            user.bothub_access_token = None
            user.state = None

            # Сохраняем изменения
            await user_repository.update(user)

            logger.info(f"Аккаунт пользователя {user.id} успешно привязан к аккаунту {data['email']}")
            return {"status": "success"}

        # Другие типы вебхуков из PHP бота
        elif data["type"] == "message":
            # Обработка сообщений (например, ответы на запросы пользователя)
            logger.info(f"Получен вебхук типа 'message': {data}")
            # ... обработка сообщений ...
            return {"status": "success"}

        elif data["type"] == "present":
            # Обработка подарков токенов
            logger.info(f"Получен вебхук типа 'present': {data}")
            # ... обработка подарков ...
            return {"status": "success"}

        elif data["type"] == "presentViaEmail":
            # Обработка подарков через email
            logger.info(f"Получен вебхук типа 'presentViaEmail': {data}")
            # ... обработка подарков через email ...
            return {"status": "success"}

        else:
            logger.warning(f"Неизвестный тип вебхука: {data['type']}")
            return {"status": "success"}

    except HTTPException as e:
        # Пробрасываем HTTP-исключения
        raise
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука BotHub: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")