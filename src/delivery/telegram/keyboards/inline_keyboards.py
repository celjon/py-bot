import json
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional

# src/delivery/telegram/keyboards/inline_keyboards.py

def get_chat_model_inline_keyboard(models: List[Dict], current_model: Optional[str] = None) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру для выбора модели чата"""
    buttons = []

    for model in models:
        # Добавляем метку выбранной модели
        model_name = model.get("label") or model.get("id", "Неизвестная модель")
        is_selected = model.get("id") == current_model
        text = f"{model_name} {'✅' if is_selected else ''}"

        # Проверяем доступность модели
        is_allowed = model.get("is_allowed", False)
        if not is_allowed:
            text += " 🔒"

        # Уменьшаем размер callback_data, используя короткие ключи
        # t - тип (type), m - model_id, a - allowed
        callback_data = json.dumps({
            "t": "m",  # m = модель
            "m": model.get("id"),
            "a": 1 if is_allowed else 0
        })

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    # Добавляем кнопку отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=json.dumps({"t": "c"}))])  # c = cancel

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_context_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру для управления контекстом"""
    buttons = [
        [InlineKeyboardButton(
            text=f"Контекст включен {'✅' if enabled else ''}",
            callback_data=json.dumps({"action": "context_on"})
        )],
        [InlineKeyboardButton(
            text=f"Контекст выключен {'✅' if not enabled else ''}",
            callback_data=json.dumps({"action": "context_off"})
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=json.dumps({"action": "cancel"})
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)