# src/services/keyboard_service.py
import logging
from typing import Dict, List, Optional, Any
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from src.domain.entity.user import User
from src.domain.service.language_service import LanguageService

logger = logging.getLogger(__name__)


class KeyboardService:
    """Сервис для создания клавиатур (аналог PHP KeyboardService)"""

    # Эмодзи-кнопки для стандартных чатов
    CHAT_BUTTONS = {'1️⃣': 1, '2️⃣': 2, '3️⃣': 3, '4️⃣': 4, '📝': 5}

    def __init__(self):
        """Инициализация сервиса клавиатур"""
        self.is_web_search = False

    def set_is_web_search(self, enabled: bool) -> None:
        """
        Установить флаг веб-поиска

        Args:
            enabled: Включен ли веб-поиск
        """
        self.is_web_search = enabled

    def get_main_keyboard(self, lang: LanguageService, user: Optional[User] = None) -> ReplyKeyboardMarkup:
        """
        Получить основную клавиатуру бота

        Args:
            lang: Сервис локализации
            user: Пользователь (опционально)

        Returns:
            ReplyKeyboardMarkup: Клавиатура
        """
        # Получаем текущий индекс чата
        current_chat_index = user.current_chat_index if user else 1

        # Создаем кнопки чатов с маркером текущего чата
        chat_buttons = []
        for emoji, index in self.CHAT_BUTTONS.items():
            if index == current_chat_index:
                chat_buttons.append(KeyboardButton(text=f"{emoji}✅"))
            else:
                chat_buttons.append(KeyboardButton(text=emoji))

        # Создаем основную клавиатуру
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                chat_buttons,
                [KeyboardButton(text="🔄 Новый чат"), KeyboardButton(text="⚙️ Сменить модель")],
                [KeyboardButton(text="🔗 Привязать аккаунт")]
            ],
            resize_keyboard=True
        )

        # Если включен веб-поиск, добавляем кнопку
        if self.is_web_search:
            keyboard.keyboard.append([KeyboardButton(text="🔍 Поиск")])

        return keyboard