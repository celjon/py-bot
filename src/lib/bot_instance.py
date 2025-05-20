import logging
from typing import Optional
from aiogram import Bot
from src.config.settings import Settings

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота
_bot_instance: Optional[Bot] = None


def set_bot_instance(bot: Bot) -> None:
    """
    Устанавливает глобальный экземпляр бота

    Args:
        bot: Экземпляр бота
    """
    global _bot_instance
    _bot_instance = bot
    logger.info("Глобальный экземпляр бота установлен")


def get_bot_instance() -> Optional[Bot]:
    """
    Получает глобальный экземпляр бота

    Returns:
        Optional[Bot]: Экземпляр бота или None если не установлен
    """
    global _bot_instance
    return _bot_instance


def is_bot_available() -> bool:
    """
    Проверяет, доступен ли экземпляр бота

    Returns:
        bool: True если бот доступен
    """
    return _bot_instance is not None