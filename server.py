import os
import uvicorn
import logging
import json
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime

from src.config.settings import get_settings
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.present_repository import PresentRepository
from src.lib.clients.telegram_client import TelegramClient
from src.domain.service.language_service import LanguageService
from src.services.keyboard_service import KeyboardService
from src.lib.bot_instance import get_bot_instance
from src.domain.entity.present import Present

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
settings = get_settings()
app = FastAPI(title="BotHub WebHook Server", version="1.0.0")

# Инициализация клиентов и сервисов
tg_client = TelegramClient(settings.TELEGRAM_TOKEN, settings.TELEGRAM_API_URL)
keyboard_service = KeyboardService()


@app.post("/bothub-webhook")
async def bothub_webhook(
        request: Request,
        botsecretkey: Optional[str] = Header(None)
):
    """Обработчик вебхуков от BotHub (аналог PHP WebhookController.php)"""
    try:
        # Проверяем секретный ключ
        if not botsecretkey or botsecretkey != settings.BOTHUB_SECRET_KEY:
            logger.error(f"Неверный секретный ключ: {botsecretkey}")
            return JSONResponse(
                status_code=400,
                content={"error": "Incorrect Bothub webhook data (incorrect secret key)"}
            )

        # Получаем данные
        try:
            body = await request.body()
            data = json.loads(body.decode('utf-8'))
            logger.info(f"Webhook data: {data}")
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": "Некорректные данные"}
            )

        # Проверяем наличие обязательных полей
        if not data or "type" not in data:
            logger.error("Отсутствует поле 'type'")
            return JSONResponse(
                status_code=400,
                content={"error": "Incorrect Bothub webhook data: missing type"}
            )

        # Проверяем, предназначен ли запрос для Python-бота
        # Для обратной совместимости принимаем как флаг pythonBot: true, так и запросы без этого флага
        is_python_bot = data.get("pythonBot", False)

        # Для запросов типа "merge" всегда проверяем флаг pythonBot
        if data["type"] == "merge" and not is_python_bot:
            logger.info(f"Получен запрос merge без флага pythonBot, возможно это запрос для PHP-бота")
            # Если у вас есть специальная обработка для PHP-бота, можно добавить здесь
            # Либо просто игнорировать такие запросы
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "message": "This merge request is not intended for Python bot"}
            )

        # Обработка разных типов вебхуков
        webhook_type = data["type"]

        # Инициализируем репозитории
        user_repository = UserRepository()
        present_repository = PresentRepository()

        if webhook_type == "merge":
            # Обработка слияния аккаунтов (как в PHP bothubHook)
            return await handle_merge_webhook(data, user_repository)

        elif webhook_type == "present":
            # Обработка подарка токенов
            return await handle_present_webhook(data, user_repository, present_repository)

        elif webhook_type == "presentViaEmail":
            # Обработка подарка по email
            return await handle_present_via_email_webhook(data, user_repository)

        elif webhook_type == "message":
            # Обработка сообщения от BotHub
            return await handle_message_webhook(data, user_repository)

        else:
            logger.error(f"Неизвестный тип вебхука: {webhook_type}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Incorrect Bothub webhook data: unknown type {webhook_type}"}
            )

    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Внутренняя ошибка: {str(e)}"}
        )


async def handle_merge_webhook(data: Dict[str, Any], user_repository: UserRepository):
    """Обработка слияния аккаунтов"""
    # Проверяем обязательные поля
    required_fields = ["oldId", "newId", "email"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"Отсутствуют поля: {missing_fields}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Incorrect Bothub webhook data: missing fields {missing_fields}"}
        )

    old_id = data["oldId"]
    new_id = data["newId"]
    email = data["email"]

    # Флаг, указывающий что запрос для Python-бота
    is_python_bot = data.get("pythonBot", False)

    logger.info(f"Merge: {old_id} -> {new_id} ({email}), Python bot: {is_python_bot}")

    # Расширенное логирование для отладки
    try:
        all_users = await user_repository.get_all(limit=10, offset=0)
        logger.info(f"Все пользователи в БД: {[(u.id, u.bothub_id) for u in all_users]}")
        logger.info(f"Ищем пользователя с bothub_id={old_id}")
    except Exception as e:
        logger.warning(f"Не удалось получить список пользователей: {e}")

    # Находим пользователя
    user = None
    try:
        # Сначала ищем по bothub_id
        user = await user_repository.find_by_bothub_id(old_id)

        if not user and is_python_bot:
            # Если это запрос для Python-бота и пользователь не найден по старому ID,
            # пробуем найти по TG ID (т.к. oldId может быть TG ID, а не bothub_id)
            logger.info(f"Пользователь не найден по bothub_id, пробуем найти по tg_id: {old_id}")
            user = await user_repository.find_by_tg_id(old_id)
    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Ошибка поиска пользователя: {str(e)}"}
        )

    if not user:
        logger.error(f"Пользователь с id={old_id} не найден (ни как bothub_id, ни как tg_id)")
        return JSONResponse(
            status_code=404,
            content={"error": "Пользователь не найден"}
        )

    # Обновляем данные пользователя
    user.bothub_id = new_id
    user.email = email
    user.bothub_access_token = None  # Сбрасываем токен
    user.state = None  # Сбрасываем состояние

    try:
        # Сохраняем изменения
        await user_repository.update(user)
        logger.info(f"Данные пользователя {user.id} успешно обновлены, новый bothub_id: {new_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных пользователя: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Ошибка обновления данных: {str(e)}"}
        )

    try:
        # Отправляем уведомление пользователю
        language_service = LanguageService(user.language_code or "en")
        content = language_service.get_string("accounts_merged", [user.email])

        # Создаем словарь клавиатуры
        keyboard_buttons = [
            [{"text": "🔄 Новый чат"}, {"text": "⚙️ Сменить модель"}],
            [{"text": "🔗 Привязать аккаунт"}]
        ]
        keyboard = {"keyboard": keyboard_buttons, "resize_keyboard": True}

        # Отправляем сообщение
        await tg_client.send_message(
            chat_id=user.tg_id,
            text=content,
            reply_markup=keyboard
        )

        logger.info(f"Аккаунт {user.id} успешно привязан к {email}, уведомление отправлено")

        return {"status": "success", "message": "Account connected"}
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}", exc_info=True)
        # Возвращаем успех даже если не удалось отправить уведомление,
        # так как важнее сохранить изменения в БД
        return {"status": "success", "message": "Account connected, notification failed"}


async def handle_present_webhook(
        data: Dict[str, Any],
        user_repository: UserRepository,
        present_repository: PresentRepository
):
    """Обработка подарка токенов (аналог PHP present)"""
    # Проверяем обязательные поля
    required_fields = ["userId", "tokens", "fromUserId"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"Отсутствуют поля: {missing_fields}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Incorrect Bothub webhook data: missing fields {missing_fields}"}
        )

    from_user_id = data["fromUserId"]
    user_id = data["userId"]
    tokens = data["tokens"]
    via_email = data.get("viaEmail", False)

    # Находим отправителя
    from_user = await user_repository.find_by_bothub_id(from_user_id)
    if not from_user:
        logger.error(f"Отправитель с bothub_id={from_user_id} не найден")
        return JSONResponse(
            status_code=404,
            content={"error": "Отправитель не найден"}
        )

    # Локализация для отправителя
    from_user_lang = LanguageService(from_user.language_code or "en")
    from_user_keyboard = keyboard_service.get_main_keyboard(from_user_lang, from_user)

    if via_email:
        # Подарок по email
        content = from_user_lang.get_string("present_done_email")
        await tg_client.send_message(
            chat_id=from_user.tg_id,
            text=content,
            reply_markup=from_user_keyboard
        )
    else:
        # Подарок другому пользователю
        user = await user_repository.find_by_bothub_id(user_id)
        if not user:
            logger.error(f"Получатель с bothub_id={user_id} не найден")
            return JSONResponse(
                status_code=404,
                content={"error": "Получатель не найден"}
            )

        # Добавляем подарок
        present = await add_present(user, tokens, present_repository)

        # Локализация для получателя
        user_lang = LanguageService(user.language_code or "en")
        user_keyboard = keyboard_service.get_main_keyboard(user_lang, user)

        # Сообщение отправителю
        sender_content = from_user_lang.get_string("present_done")
        await tg_client.send_message(
            chat_id=from_user.tg_id,
            text=sender_content,
            reply_markup=from_user_keyboard
        )

        # Сообщение о возможности повторного уведомления
        resend_content = from_user_lang.get_string("present_resend_notification")
        await tg_client.send_message(
            chat_id=from_user.tg_id,
            text=resend_content,
            reply_markup=from_user_keyboard
        )

    return {"status": "success", "message": "Present processed"}


async def handle_present_via_email_webhook(data: Dict[str, Any], user_repository: UserRepository):
    """Обработка подарка по email (аналог PHP presentViaEmail)"""
    # Проверяем обязательные поля
    required_fields = ["userId", "tokens", "fromUserId"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"Отсутствуют поля: {missing_fields}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Incorrect Bothub webhook data: missing fields {missing_fields}"}
        )

    from_user_id = data["fromUserId"]

    # Находим отправителя
    from_user = await user_repository.find_by_bothub_id(from_user_id)
    if not from_user:
        logger.error(f"Отправитель с bothub_id={from_user_id} не найден")
        return JSONResponse(
            status_code=404,
            content={"error": "Отправитель не найден"}
        )

    # Локализация для отправителя
    from_user_lang = LanguageService(from_user.language_code or "en")
    from_user_keyboard = keyboard_service.get_main_keyboard(from_user_lang, from_user)

    # Сообщение отправителю
    content = from_user_lang.get_string("present_done_email")
    await tg_client.send_message(
        chat_id=from_user.tg_id,
        text=content,
        reply_markup=from_user_keyboard
    )

    return {"status": "success", "message": "Present via email processed"}


async def handle_message_webhook(data: Dict[str, Any], user_repository: UserRepository):
    """Обработка сообщения от BotHub (аналог PHP message)"""
    # Проверка обязательных полей
    if (
            "message" not in data or
            "additional_content" not in data["message"] or
            "relatedMessageId" not in data or
            "chat_id" not in data["message"] or
            "content" not in data["message"]["additional_content"]
    ):
        logger.error(f"Отсутствуют обязательные поля в сообщении")
        return JSONResponse(
            status_code=400,
            content={"error": "Incorrect Bothub webhook data: missing required fields"}
        )

    # В полной версии здесь была бы обработка сообщений от BotHub
    # Но мы пока что просто логируем данные
    logger.info(f"Получено сообщение от BotHub: {data['message']['additional_content']['content']}")

    return {"status": "success", "message": "Message received"}


async def add_present(user, tokens, present_repository):
    """Добавить подарок пользователю"""
    present = Present(
        user_id=user.id,
        tokens=tokens,
        notified=False,
    )

    await present_repository.save(present)
    return present


@app.get("/health")
async def health_check():
    """Проверка здоровья"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    # Получаем порт из переменной окружения или используем порт по умолчанию
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)