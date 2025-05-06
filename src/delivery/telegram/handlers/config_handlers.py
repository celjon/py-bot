from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import json
import logging
from ..keyboards.inline_keyboards import get_chat_model_inline_keyboard
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

logger = logging.getLogger(__name__)


def register_config_handlers(router: Router, user_repository, chat_repository):
    """Регистрация обработчиков команд конфигурации"""

    @router.message(Command("gpt_config"))
    async def handle_gpt_config_command(message: Message):
        """Обработка команды /gpt_config для настройки моделей"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            logger.info(f"Пользователь {user.id} запросил настройку GPT моделей")

            # В реальном коде здесь будет вызов model_selection_usecase
            # Для демонстрации создадим заглушку со списком моделей
            models = [
                {
                    "id": "gpt-3.5-turbo",
                    "label": "GPT-3.5 Turbo",
                    "features": ["TEXT_TO_TEXT"],
                    "is_allowed": True
                },
                {
                    "id": "gpt-4",
                    "label": "GPT-4",
                    "features": ["TEXT_TO_TEXT"],
                    "is_allowed": True
                }
            ]

            await message.answer(
                "Выберите модель для текстовой генерации:",
                parse_mode="Markdown",
                reply_markup=get_chat_model_inline_keyboard(models, chat.bothub_chat_model)
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды gpt_config: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось получить список моделей. Попробуйте позже.",
                parse_mode="Markdown"
            )

    # Обработчик для обратной совместимости с неправильным форматом команды
    @router.message(lambda message: message.text == "/gptconfig")
    async def handle_gptconfig_command(message: Message):
        """Обработка команды /gptconfig (без подчеркивания) для обратной совместимости"""
        await handle_gpt_config_command(message)

    # Обработчик для callback-запросов от инлайн клавиатуры выбора модели
    @router.callback_query(lambda c: c.data and "select_chat_model" in c.data)
    async def handle_model_selection(callback: CallbackQuery):
        try:
            # Парсим данные callback
            data = json.loads(callback.data)
            model_id = data.get("model_id")
            is_allowed = data.get("allowed", False)

            if not is_allowed:
                await callback.answer("Эта модель недоступна")
                return

            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Сохраняем выбранную модель
            chat.bothub_chat_model = model_id
            chat.reset_context_counter()
            user.gpt_model = model_id

            await user_repository.update(user)
            await chat_repository.update(chat)

            # Закрываем инлайн клавиатуру
            await callback.message.delete_reply_markup()
            await callback.answer(f"Модель {model_id} выбрана")

            # Отправляем уведомление о выборе модели
            await callback.message.answer(
                f"✅ Модель *{model_id}* успешно выбрана.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выбрал модель {model_id}")

        except Exception as e:
            logger.error(f"Ошибка при выборе модели: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выборе модели")

    # Обработчик для отмены операции (кнопка "Отмена")
    @router.callback_query(lambda c: c.data and json.loads(c.data).get("action") == "cancel")
    async def handle_cancel_callback(callback: CallbackQuery):
        try:
            # Закрываем инлайн клавиатуру
            await callback.message.delete_reply_markup()
            await callback.answer("Операция отменена")

            # Получаем пользователя и чат
            user = await get_or_create_user(callback.message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Отправляем сообщение
            await callback.message.answer(
                "Операция отменена. Продолжим общение.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

        except Exception as e:
            logger.error(f"Ошибка при отмене операции: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при отмене операции")