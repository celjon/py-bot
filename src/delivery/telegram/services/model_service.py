import logging
from aiogram.types import Message
from typing import List, Dict, Any
from ..keyboards.main_keyboard import get_main_keyboard
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.lib.clients.bothub_client import BothubClient
from src.config.settings import get_settings
from ..services.keyboard_factory import KeyboardFactory

logger = logging.getLogger(__name__)


def get_default_model(models: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Получение модели по умолчанию, по аналогии с PHP ботом

    Args:
        models: Список моделей

    Returns:
        Dict[str, Any]: Выбранная модель
    """
    # Сначала ищем модель, которая и по умолчанию, и доступна
    for model in models:
        if (model.get("is_default", False) or model.get("isDefault", False)) and \
                (model.get("is_allowed", False) or model.get("isAllowed", False)) and \
                "TEXT_TO_TEXT" in model.get("features", []):
            return model

    # Если не нашли, то просто доступную модель
    for model in models:
        if (model.get("is_allowed", False) or model.get("isAllowed", False)) and \
                "TEXT_TO_TEXT" in model.get("features", []):
            return model

    # Если все еще ничего не нашли, возвращаем первую модель из списка или None
    return models[0] if models else None


async def show_model_selection(message, user_repository, chat_repository):
    """Показывает список моделей для выбора"""
    try:
        # Импортируем необходимые функции здесь, чтобы избежать циклических импортов
        from ..handlers.base_handlers import get_or_create_user, get_or_create_chat

        # ИСПРАВЛЕНИЕ: Получаем пользователя из message, а не callback!
        user = await get_or_create_user(message, user_repository)
        chat = await get_or_create_chat(user, chat_repository)

        logger.info(f"Пользователь {user.id} запросил настройку GPT моделей")

        # Получаем доступные модели
        settings = get_settings()
        bothub_client = BothubClient(settings)
        bothub_gateway = BothubGateway(bothub_client)

        # Получаем токен доступа и список моделей
        access_token = await bothub_gateway.get_access_token(user)
        models = await bothub_client.list_models(access_token)

        # ДОБАВЛЯЕМ ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
        logger.info(f"=== ПОЛНЫЙ ОТВЕТ API МОДЕЛЕЙ ===")
        logger.info(f"Общее количество моделей: {len(models)}")

        for i, model in enumerate(models):
            logger.info(f"--- Модель {i + 1} ---")
            logger.info(f"ID: {model.get('id')}")
            logger.info(f"Label: {model.get('label')}")
            logger.info(f"Name: {model.get('name')}")
            logger.info(f"Features: {model.get('features')}")
            logger.info(f"Is_allowed: {model.get('is_allowed')}")
            logger.info(f"Is_default: {model.get('is_default')}")
            logger.info(f"Parent_id: {model.get('parent_id')}")
            logger.info(f"Все поля: {model}")
            logger.info("---")

        # Фильтруем текстовые модели
        text_models = [
            model for model in models
            if "TEXT_TO_TEXT" in model.get("features", [])
        ]

        logger.info(f"=== ТЕКСТОВЫЕ МОДЕЛИ ПОСЛЕ ФИЛЬТРАЦИИ ===")
        logger.info(f"Количество текстовых моделей: {len(text_models)}")
        for model in text_models:
            logger.info(
                f"Текстовая модель: ID={model.get('id')}, Label={model.get('label')}, Allowed={model.get('is_allowed')}")

        if not text_models:
            await message.answer(
                "⚠️ Не удалось получить список моделей",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )
            return

        # Если у пользователя еще нет выбранной модели, выбираем модель по умолчанию
        if not chat.bothub_chat_model:
            default_model = get_default_model(text_models)
            if default_model:
                chat.bothub_chat_model = default_model.get("id")
                user.gpt_model = default_model.get("id")
                await chat_repository.update(chat)
                await user_repository.update(user)
                logger.info(f"Установлена модель по умолчанию {default_model.get('id')} для пользователя {user.id}")

        # Отправляем клавиатуру выбора модели
        keyboard = KeyboardFactory.create_model_selection(text_models, chat.bothub_chat_model)

        await message.answer(
            "Выберите модель ChatGPT",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка при получении списка моделей: {e}", exc_info=True)
        await message.answer(
            "❌ Не удалось получить список моделей. Попробуйте позже.",
            parse_mode="Markdown"
        )


# Добавим также функцию для создания нового чата с правильным выбором модели
async def create_new_chat_with_model(user, chat, bothub_gateway):
    """
    Создание нового чата с правильным выбором модели по аналогии с PHP ботом

    Args:
        user: Пользователь
        chat: Чат
        bothub_gateway: Шлюз для доступа к BotHub API
    """
    try:
        # Получаем список доступных моделей
        access_token = await bothub_gateway.get_access_token(user)
        models = await bothub_gateway.client.list_models(access_token)

        # Если у пользователя еще нет выбранной модели, выбираем модель по умолчанию
        if not chat.bothub_chat_model:
            default_model = get_default_model(models)
            if default_model:
                chat.bothub_chat_model = default_model.get("id")
                user.gpt_model = default_model.get("id")

        # Создаем чат с выбранной моделью
        await bothub_gateway.create_new_chat(user, chat)

        logger.info(f"Создан новый чат с моделью {chat.bothub_chat_model} для пользователя {user.id}")

    except Exception as e:
        logger.error(f"Ошибка при создании чата: {e}", exc_info=True)
        raise e