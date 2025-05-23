from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any, Optional
from .callback_data import CallbackData
from .callback_types import CallbackType
import logging

logger = logging.getLogger(__name__)


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
        logger.info(f"=== СОЗДАНИЕ КЛАВИАТУРЫ МОДЕЛЕЙ ===")
        logger.info(f"Входящие модели: {len(models)}")
        logger.info(f"Текущая модель: {current_model}")

        buttons = []
        filtered_count = 0

        for model in models:
            model_id = model.get("id", "")
            model_label = model.get("label", "")
            parent_id = model.get("parent_id")
            children = model.get("children", [])

            logger.info(
                f"Обрабатываем модель: ID={model_id}, Label={model_label}, Parent={parent_id}, Children={len(children)}")

            # ФИЛЬТРАЦИЯ: Пропускаем родительские модели (у которых есть дочерние)
            if children and len(children) > 0:
                logger.info(f"ФИЛЬТР: Пропускаем родительскую модель {model_id} (children: {len(children)})")
                filtered_count += 1
                continue

            # СОЗДАЕМ НАЗВАНИЕ: ID всегда показываем, плюс label если есть
            if model_label and model_label != model_id:
                # Если есть отдельный label, показываем "Label (id)"
                display_name = f"{model_label} ({model_id})"
            else:
                # Если label совпадает с id или отсутствует, показываем только id
                display_name = model_id

            # Добавляем статус (Free/Pro)
            if ":free" in model_id and "(Free)" not in display_name:
                display_name += " [Free]"

            is_selected = model_id == current_model
            is_allowed = model.get("is_allowed", False)

            # Создаем текст кнопки
            button_text = display_name
            if is_selected:
                button_text += " ✅"
            if not is_allowed:
                button_text += " 🔒"

            logger.info(f"ДОБАВЛЯЕМ кнопку: {button_text}")

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

        logger.info(f"=== ИТОГО ===")
        logger.info(f"Отфильтровано: {filtered_count}")
        logger.info(f"Добавлено кнопок: {len(buttons)}")

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