# src/delivery/telegram/handlers/config_handlers.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums.chat_action import ChatAction
import logging
from ..services.keyboard_factory import KeyboardFactory
from ..services.callback_data import CallbackData
from ..services.callback_types import CallbackType
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, get_or_create_user_from_callback
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.lib.clients.bothub_client import BothubClient
from src.config.settings import get_settings
from src.domain.usecase.chat_session import ChatSessionUseCase

logger = logging.getLogger(__name__)


async def show_model_selection(message, user_repository, chat_repository):
    """Показывает список моделей для выбора"""
    try:
        # Получаем пользователя из message
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

        # Фильтруем текстовые модели
        text_models = [
            model for model in models
            if "TEXT_TO_TEXT" in model.get("features", [])
        ]

        logger.info(f"Количество текстовых моделей: {len(text_models)}")

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


def get_default_model(models):
    """Получение модели по умолчанию"""
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


def register_config_handlers(router: Router, user_repository, chat_repository):
    """Регистрация обработчиков команд конфигурации"""

    @router.message(F.text == "⚙️ Сменить модель")
    async def handle_change_model_button(message: Message):
        """Обработка нажатия на кнопку смены модели"""
        await show_model_selection(message, user_repository, chat_repository)

    @router.message(Command("gpt_config"))
    async def handle_gpt_config(message: Message):
        """Обработка команды /gpt_config для настройки моделей"""
        await show_model_selection(message, user_repository, chat_repository)

    def callback_with_type(callback_type):
        async def check(callback: CallbackQuery):
            try:
                data = CallbackData.decode(callback.data)
                return data.type == callback_type
            except:
                return False

        return check

    @router.callback_query(callback_with_type(CallbackType.MODEL_SELECTION))
    async def handle_model_selection(callback: CallbackQuery):
        try:
            data = CallbackData.decode(callback.data)
            model_id = data.data.get("id")

            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            chat.bothub_chat_model = model_id
            chat.reset_context_counter()
            user.gpt_model = model_id

            await user_repository.update(user)
            await chat_repository.update(chat)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"Выбрана модель *{model_id}*. Создаю новый чат...")

            await callback.message.bot.send_chat_action(callback.message.chat.id, ChatAction.TYPING)

            settings = get_settings()
            bothub_client = BothubClient(settings)
            bothub_gateway = BothubGateway(bothub_client)
            chat_session = ChatSessionUseCase(bothub_gateway)

            await chat_session.create_new_chat(user, chat)

            model_info = f"Начат новый чат с моделью *{model_id}*"
            context_info = "\n\nКонтекст включен. /reset для сброса." if chat.context_remember else "\n\nКонтекст отключен."

            await callback.message.answer(
                f"{model_info}{context_info}",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} выбрал модель {model_id}")

        except Exception as e:
            logger.error(f"Ошибка при выборе модели: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при выборе модели")

    @router.callback_query(callback_with_type(CallbackType.UNAVAILABLE_MODEL))
    async def handle_unavailable_model(callback: CallbackQuery):
        await callback.answer("⛔ Эта модель недоступна в вашем тарифе")

    @router.callback_query(callback_with_type(CallbackType.CANCEL))
    async def handle_cancel(callback: CallbackQuery):
        try:
            user = await get_or_create_user_from_callback(callback, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Операция отменена", reply_markup=get_main_keyboard(user, chat))
        except Exception as e:
            logger.error(f"Ошибка при отмене: {e}", exc_info=True)
            await callback.answer("Произошла ошибка")