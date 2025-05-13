from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime

from src.config.settings import get_settings, Settings
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
from src.adapter.repository.present_repository import PresentRepository
from src.domain.usecase.present import PresentUseCase
from src.domain.entity.user import User
from src.lib.clients.bothub_client import BothubClient
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.domain.usecase.chat_session import ChatSessionUseCase

# Создаем роутер
router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


# Репозитории
async def get_user_repository(settings: Settings = Depends(get_settings)):
    db_path = settings.DB_PATH
    repository = UserRepository(db_path)
    return repository


async def get_chat_repository(settings: Settings = Depends(get_settings)):
    db_path = settings.DB_PATH
    repository = ChatRepository(db_path)
    return repository


async def get_present_repository(settings: Settings = Depends(get_settings)):
    db_path = settings.DB_PATH
    repository = PresentRepository(db_path)
    return repository


# Гейтвеи
async def get_bothub_gateway(settings: Settings = Depends(get_settings)):
    client = BothubClient(settings)
    gateway = BothubGateway(client)
    return gateway


# Юзкейсы
async def get_present_usecase(
        present_repository: PresentRepository = Depends(get_present_repository),
        bothub_gateway: BothubGateway = Depends(get_bothub_gateway)
):
    return PresentUseCase(present_repository, bothub_gateway)


async def get_chat_session_usecase(
        bothub_gateway: BothubGateway = Depends(get_bothub_gateway)
):
    return ChatSessionUseCase(bothub_gateway)


@router.post("/bothub-webhook")
async def bothub_webhook(
        request: Request,
        settings: Settings = Depends(get_settings),
        user_repository: UserRepository = Depends(get_user_repository),
        chat_repository: ChatRepository = Depends(get_chat_repository),
        present_usecase: PresentUseCase = Depends(get_present_usecase),
        chat_session_usecase: ChatSessionUseCase = Depends(get_chat_session_usecase),
        botsecretkey: Optional[str] = Header(None)
):
    """Обработчик вебхуков от BotHub"""
    try:
        # Проверяем секретный ключ
        if not botsecretkey or botsecretkey != settings.BOTHUB_SECRET_KEY:
            logger.error(f"Неверный секретный ключ вебхука: {botsecretkey}")
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

            # Отправляем уведомление пользователю
            from aiogram import Bot
            bot = Bot(token=settings.TELEGRAM_TOKEN)
            try:
                # Формируем локализованное сообщение
                lang = user.language_code or "en"
                message = f"🔗 Ваш аккаунт успешно привязан к аккаунту {user.email}" if lang == "ru" else f"🔗 Your account has been successfully linked to {user.email}"

                # Отправляем сообщение пользователю
                if user.telegram_id:
                    await bot.send_message(chat_id=user.telegram_id, text=message)
                    logger.info(f"Отправлено уведомление пользователю {user.id} о привязке аккаунта")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления: {e}")
            finally:
                await bot.session.close()

            logger.info(f"Аккаунт пользователя {user.id} успешно привязан к аккаунту {data['email']}")
            return {"status": "success"}

        # Обработка вебхука message
        elif data["type"] == "message":
            # Проверка обязательных полей
            if (not data.get("message") or not data["message"].get("additional_content") or
                    not data.get("relatedMessageId") or not data["message"].get("chat_id") or
                    not data["message"]["additional_content"].get("content")):
                logger.error(f"Некорректные данные для типа 'message': {data}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука для типа 'message'"}
                )

            # Получаем связанное сообщение
            related_message_id = int(data["relatedMessageId"])
            # Здесь должен быть код для получения связанного сообщения
            # В текущей реализации просто логируем и возвращаем успех
            logger.info(f"Получен вебхук message с relatedMessageId={related_message_id}")

            # Получаем chat_id из данных сообщения
            chat_id = data["message"]["chat_id"]

            # Проверяем наличие изображений
            if data["message"]["additional_content"].get("imageUrls"):
                logger.info(f"Получены изображения: {len(data['message']['additional_content']['imageUrls'])}")
                # Здесь должен быть код для отправки изображений

            return {"status": "success"}

        # Обработка вебхука present (подарок токенов)
        elif data["type"] == "present":
            # Проверка обязательных полей
            if not data.get("userId") or not data.get("tokens") or not data.get("fromUserId"):
                logger.error(f"Некорректные данные для типа 'present': {data}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука для типа 'present'"}
                )

            # Обрабатываем подарок через email или через telegram
            if data.get("viaEmail"):
                # Подарок через email
                from_user = await user_repository.find_by_bothub_id(data["fromUserId"])
                if not from_user:
                    logger.error(f"Пользователь-отправитель с bothub_id={data['fromUserId']} не найден")
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Пользователь-отправитель не найден"}
                    )

                # Отправляем уведомление отправителю
                from aiogram import Bot
                bot = Bot(token=settings.TELEGRAM_TOKEN)
                try:
                    # Формируем локализованное сообщение
                    lang = from_user.language_code or "en"
                    message = "🎁 Подарок успешно отправлен на указанный email!" if lang == "ru" else "🎁 Gift successfully sent to the specified email!"

                    # Отправляем сообщение
                    if from_user.telegram_id:
                        await bot.send_message(chat_id=from_user.telegram_id, text=message)
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления: {e}")
                finally:
                    await bot.session.close()
            else:
                # Подарок через Telegram
                user = await user_repository.find_by_bothub_id(data["userId"])
                if not user:
                    logger.error(f"Пользователь-получатель с bothub_id={data['userId']} не найден")
                    return JSONResponse(
                        status_code=404,
                        content={"error": "Пользователь-получатель не найден"}
                    )

                # Добавляем подарок
                await present_usecase.add_present(user, int(data["tokens"]))

                # Отправляем уведомление отправителю
                from_user = await user_repository.find_by_bothub_id(data["fromUserId"])
                if from_user:
                    from aiogram import Bot
                    bot = Bot(token=settings.TELEGRAM_TOKEN)
                    try:
                        # Формируем локализованное сообщение
                        lang = from_user.language_code or "en"
                        message = "🎁 Подарок успешно отправлен!" if lang == "ru" else "🎁 Gift successfully sent!"

                        # Отправляем сообщение
                        if from_user.telegram_id:
                            await bot.send_message(chat_id=from_user.telegram_id, text=message)
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления: {e}")
                    finally:
                        await bot.session.close()

            return {"status": "success"}

        # Обработка вебхука presentViaEmail (подарок токенов через email)
        elif data["type"] == "presentViaEmail":
            # Проверка обязательных полей
            if not data.get("userId") or not data.get("tokens") or not data.get("fromUserId"):
                logger.error(f"Некорректные данные для типа 'presentViaEmail': {data}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Некорректные данные вебхука для типа 'presentViaEmail'"}
                )

            # Находим отправителя
            from_user = await user_repository.find_by_bothub_id(data["fromUserId"])
            if not from_user:
                logger.error(f"Пользователь-отправитель с bothub_id={data['fromUserId']} не найден")
                return JSONResponse(
                    status_code=404,
                    content={"error": "Пользователь-отправитель не найден"}
                )

            # Отправляем уведомление
            from aiogram import Bot
            bot = Bot(token=settings.TELEGRAM_TOKEN)
            try:
                # Формируем локализованное сообщение
                lang = from_user.language_code or "en"
                message = "🎁 Подарок успешно отправлен на указанный email!" if lang == "ru" else "🎁 Gift successfully sent to the specified email!"

                # Отправляем сообщение
                if from_user.telegram_id:
                    await bot.send_message(chat_id=from_user.telegram_id, text=message)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления: {e}")
            finally:
                await bot.session.close()

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


@router.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "ok"}