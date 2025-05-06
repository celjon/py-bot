import json
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional

def get_chat_model_inline_keyboard(models: List[Dict], current_model: Optional[str] = None) -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру для выбора модели чата"""
    buttons = []

    # Фильтруем только модели для текстовой генерации
    text_models = [model for model in models if "TEXT_TO_TEXT" in model.get("features", [])]

    for model in text_models:
        # Добавляем метку выбранной модели
        model_name = model.get("label") or model.get("id", "Неизвестная модель")
        is_selected = model.get("id") == current_model
        text = f"{model_name} {'✅' if is_selected else ''}"

        # Проверяем доступность модели
        is_allowed = model.get("is_allowed", False)
        if not is_allowed:
            text += " 🔒"

        callback_data = json.dumps({
            "action": "select_chat_model",
            "model_id": model.get("id"),
            "allowed": is_allowed
        })

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    # Добавляем кнопку отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=json.dumps({"action": "cancel"}))])

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