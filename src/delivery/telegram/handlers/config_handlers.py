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

            # Получаем токен доступа пользователя через BothubGateway
            from src.adapter.gateway.bothub_gateway import BothubGateway
            from src.lib.clients.bothub_client import BothubClient
            from src.config.settings import get_settings

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)

            # Получаем список моделей от сервера
            access_token = await bothub_gateway.get_access_token(user)
            models_response = await bothub_client.list_models(access_token)

            # Фильтруем только текстовые модели
            text_models = [
                model for model in models_response
                if "TEXT_TO_TEXT" in model.get("features", [])
            ]

            # Если нет моделей, сообщаем об ошибке
            if not text_models:
                await message.answer(
                    "⚠️ Не удалось получить список доступных моделей. Попробуйте позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            await message.answer(
                "Выберите модель для текстовой генерации:",
                parse_mode="Markdown",
                reply_markup=get_chat_model_inline_keyboard(text_models, chat.bothub_chat_model)
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
    # src/delivery/telegram/handlers/config_handlers.py

    # Обработчик для callback-запросов от инлайн клавиатуры выбора модели
    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "m")
    async def handle_model_selection(callback: CallbackQuery):
        try:
            # Парсим данные callback
            data = json.loads(callback.data)
            model_id = data.get("m")  # m = model_id
            is_allowed = data.get("a") == 1  # a = allowed (1 = True, 0 = False)

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
            await callback.message.edit_reply_markup(reply_markup=None)
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

    # Обработчик для кнопки отмены
    @router.callback_query(lambda c: c.data and json.loads(c.data).get("t") == "c")
    async def handle_cancel_callback(callback: CallbackQuery):
        try:
            # Закрываем инлайн клавиатуру
            await callback.message.edit_reply_markup(reply_markup=None)
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