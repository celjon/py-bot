import logging
from aiogram.types import Message
from typing import List, Dict, Any

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