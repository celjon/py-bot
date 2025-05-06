# src/delivery/telegram/services/keyboard_factory.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any, Optional
from .callback_data import CallbackData
from .callback_types import CallbackType


class KeyboardFactory:
    """Фабрика для создания клавиатур"""

    @staticmethod
    def create_model_selection(models: List[Dict[str, Any]],
                               current_model: Optional[str] = None) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для выбора модели

        Args:
            models: Список моделей
            current_model: Текущая модель

        Returns:
            InlineKeyboardMarkup: Клавиатура для выбора модели
        """
        buttons = []

        for model in models:
            model_id = model.get("id", "")
            model_name = model.get("label") or model_id
            is_selected = model_id == current_model
            is_allowed = model.get("is_allowed", False)

            # Создаем текст кнопки
            button_text = f"{model_name}"
            if is_selected:
                button_text += " ✅"
            if not is_allowed:
                button_text += " 🔒"

            # Создаем callback-данные
            if is_allowed:
                callback_data = CallbackData(
                    type=CallbackType.MODEL_SELECTION,
                    data={"id": model_id}
                ).encode()
            else:
                callback_data = CallbackData(
                    type=CallbackType.UNAVAILABLE_MODEL,
                    data={"id": model_id}
                ).encode()

            buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

        # Добавляем кнопку отмены
        cancel_data = CallbackData(type=CallbackType.CANCEL).encode()
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def create_context_keyboard(context_enabled: bool) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру для управления контекстом

        Args:
            context_enabled: Включен ли контекст

        Returns:
            InlineKeyboardMarkup: Клавиатура для управления контекстом
        """
        on_data = CallbackData(type=CallbackType.CONTEXT_ON).encode()
        off_data = CallbackData(type=CallbackType.CONTEXT_OFF).encode()
        cancel_data = CallbackData(type=CallbackType.CANCEL).encode()

        buttons = [
            [InlineKeyboardButton(
                text=f"Запоминать контекст {'✅' if context_enabled else ''}",
                callback_data=on_data
            )],
            [InlineKeyboardButton(
                text=f"Не запоминать контекст {'✅' if not context_enabled else ''}",
                callback_data=off_data
            )],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)