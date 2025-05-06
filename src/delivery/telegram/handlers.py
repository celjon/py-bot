# src/delivery/telegram/handlers.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums.chat_action import ChatAction
from src.domain.service.intent_detection import IntentDetectionService, IntentType
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.account_connection import AccountConnectionUseCase
from src.domain.usecase.image_generation import ImageGenerationUseCase
from src.domain.usecase.web_search import WebSearchUseCase
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
import logging
import json
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Создаём роутер для aiogram
dp = Router()


def create_handlers(
        chat_session_usecase: ChatSessionUseCase,
        account_connection_usecase: AccountConnectionUseCase,
        image_generation_usecase: ImageGenerationUseCase,
        web_search_usecase: WebSearchUseCase,
        intent_detection_service: IntentDetectionService,
        user_repository: UserRepository,
        chat_repository: ChatRepository
):
    """Фабричный метод для создания обработчиков сообщений Telegram"""

    # ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

    async def get_or_create_user(message: Message) -> User:
        """Получение или создание пользователя из сообщения Telegram"""
        telegram_id = str(message.from_user.id)
        user = await user_repository.find_by_telegram_id(telegram_id)

        if not user:
            user = User(
                id=0,  # Временный ID, будет заменён после сохранения
                telegram_id=telegram_id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username,
                language_code=message.from_user.language_code,
                current_chat_index=1
            )
            user_id = await user_repository.save(user)
            user.id = user_id

        return user

    async def get_or_create_chat(user: User) -> Chat:
        """Получение или создание чата для пользователя"""
        chat = await chat_repository.find_by_user_id_and_chat_index(
            user.id,
            user.current_chat_index
        )

        if not chat:
            chat = Chat(
                id=0,  # Временный ID, будет заменён после сохранения
                user_id=user.id,
                chat_index=user.current_chat_index
            )
            chat_id = await chat_repository.save(chat)
            chat.id = chat_id

        return chat

    async def send_long_message(message: Message, content: str):
        """Отправляет длинное сообщение, разбивая его на части, если необходимо."""
        if len(content) <= 3900:  # Уменьшенный порог для учета Markdown
            await message.answer(content, parse_mode="Markdown")
            return

        parts = []
        while content:
            if len(content) <= 3900:
                parts.append(content)
                content = ""
            else:
                last_newline = content[:3900].rfind("\n")
                if last_newline == -1:
                    last_newline = 3900
                parts.append(content[:last_newline])
                content = content[last_newline:]

        for part in parts:
            await message.answer(part, parse_mode="Markdown")

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

    def get_image_model_inline_keyboard(models: List[Dict],
                                        current_model: Optional[str] = None) -> InlineKeyboardMarkup:
        """Возвращает инлайн-клавиатуру для выбора модели генерации изображений"""
        buttons = []

        # Фильтруем только модели для генерации изображений
        image_models = [model for model in models if "TEXT_TO_IMAGE" in model.get("features", [])]

        for model in image_models:
            # Добавляем метку выбранной модели
            model_name = model.get("label") or model.get("id", "Неизвестная модель")
            is_selected = model.get("id") == current_model
            text = f"{model_name} {'✅' if is_selected else ''}"

            # Проверяем доступность модели
            is_allowed = model.get("is_allowed", False)
            if not is_allowed:
                text += " 🔒"

            callback_data = json.dumps({
                "action": "select_image_model",
                "model_id": model.get("id"),
                "allowed": is_allowed
            })

            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

        # Добавляем кнопку отмены
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=json.dumps({"action": "cancel"}))])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_web_search_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
        """Возвращает инлайн-клавиатуру для управления веб-поиском"""
        buttons = [
            [InlineKeyboardButton(
                text=f"🔍 Веб-поиск {'✅' if enabled else '❌'}",
                callback_data=json.dumps({"action": "toggle_web_search"})
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=json.dumps({"action": "cancel"})
            )]
        ]
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

    # ==================== ОБРАБОТЧИКИ КОМАНД ====================

    @dp.message(Command("start"))
    async def handle_start_command(message: Message):
        """Обработка команды /start"""
        try:
            user = await get_or_create_user(message)
            # Проверяем наличие реферального кода
            if message.text and len(message.text.split()) > 1:
                user.referral_code = message.text.split()[1]
                await user_repository.update(user)

            await message.answer(
                "👋 Привет! Я BotHub, умный ассистент на базе нейросетей.\n\n"
                "✨ Я могу:\n"
                "📝 Общаться с вами, отвечать на вопросы\n"
                "🔍 Искать информацию в интернете\n"
                "🎨 Генерировать изображения\n\n"
                "Просто напишите мне, что вы хотите, и я автоматически определю ваше намерение!\n\n"
                "Полезные команды:\n"
                "/reset - сбросить контекст разговора\n"
                "/help - получить справку\n"
                "/gpt_config - настройка моделей для текста\n"
                "/image_generation_config - настройка моделей для изображений\n"
                "/context - управление контекстом\n"
                "/web_search - управление веб-поиском",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка обработки команды /start: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке команды",
                parse_mode="Markdown"
            )

    @dp.message(Command("reset"))
    async def handle_reset_command(message: Message):
        """Обработка команды /reset для сброса контекста"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Сбрасываем счетчик контекста и контекст на сервере BotHub
            await chat_session_usecase.reset_context(user, chat)
            await chat_repository.update(chat)

            await message.answer(
                "🔄 Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка сброса контекста: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    @dp.message(Command("link_account"))
    async def handle_link_account_command(message: Message):
        """Обработка команды /link_account для привязки аккаунта"""
        try:
            user = await get_or_create_user(message)

            # Если у пользователя уже есть email, значит аккаунт уже подключен
            if user.email:
                await message.answer(
                    "Ваш аккаунт Telegram уже привязан к аккаунту BotHub.",
                    parse_mode="Markdown"
                )
                return

            try:
                # Генерируем ссылку для подключения
                link = await account_connection_usecase.generate_connection_link(user)

                # Отправляем сообщение с ссылкой, избегая использования Markdown
                await message.answer(
                    f"Для привязки вашего Telegram к существующему аккаунту BotHub, перейдите по ссылке:\n\n{link}\n\n"
                    f"После привязки вы сможете использовать ваши токены из аккаунта BotHub.",
                    parse_mode=None
                )
            except Exception as link_error:
                logger.error(f"Ошибка при генерации ссылки: {link_error}", exc_info=True)
                await message.answer(
                    f"Не удалось сгенерировать ссылку для привязки. \n\n"
                    f"Вы можете вручную привязать аккаунт:\n"
                    f"1) Войдите в аккаунт на сайте bothub.chat\n"
                    f"2) Перейдите в настройки профиля\n"
                    f"3) Найдите раздел 'Подключенные аккаунты'\n"
                    f"4) Добавьте Telegram и следуйте инструкциям",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды link_account: {e}", exc_info=True)
            await message.answer(
                "Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

    @dp.message(Command("gpt_config"))
    async def handle_gpt_config_command(message: Message):
        """Обработка команды /gpt_config для настройки моделей"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем список доступных моделей
            access_token = await chat_session_usecase.gateway.get_access_token(user)
            models = await chat_session_usecase.gateway.client.list_models(access_token)

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

    @dp.message(Command("image_generation_config"))
    async def handle_image_generation_config_command(message: Message):
        """Обработка команды /image_generation_config для настройки моделей генерации изображений"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем список доступных моделей
            access_token = await chat_session_usecase.gateway.get_access_token(user)
            models = await chat_session_usecase.gateway.client.list_models(access_token)

            await message.answer(
                "Выберите модель для генерации изображений:",
                parse_mode="Markdown",
                reply_markup=get_image_model_inline_keyboard(models, user.image_generation_model)
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке команды image_generation_config: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось получить список моделей. Попробуйте позже.",
                parse_mode="Markdown"
            )

    @dp.message(Command("context"))
    async def handle_context_command(message: Message):
        """Обработка команды /context для управления контекстом"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            await message.answer(
                "Управление контекстом:\n\n"
                "Контекст позволяет боту помнить предыдущие сообщения в текущем разговоре. "
                "Вы можете включить или выключить запоминание контекста.",
                parse_mode="Markdown",
                reply_markup=get_context_inline_keyboard(chat.context_remember)
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке команды context: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

    @dp.message(Command("web_search"))
    async def handle_web_search_command(message: Message):
        """Обработка команды /web_search для управления веб-поиском"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем текущий статус веб-поиска
            web_search_enabled = await web_search_usecase.gateway.get_web_search(user, chat)

            await message.answer(
                "Управление веб-поиском:\n\n"
                "Веб-поиск позволяет боту искать информацию в интернете для ответа на ваши вопросы.",
                parse_mode="Markdown",
                reply_markup=get_web_search_inline_keyboard(web_search_enabled)
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке команды web_search: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

    @dp.message(Command("help"))
    async def handle_help_command(message: Message):
        """Обработка команды /help для вывода справки"""
        try:
            await message.answer(
                "📚 *Справка по командам бота*\n\n"
                "/start - Начать общение с ботом\n"
                "/reset - Сбросить контекст разговора\n"
                "/link_account - Привязать аккаунт Telegram к существующему аккаунту BotHub\n"
                "/gpt_config - Настройка моделей для текстовой генерации\n"
                "/image_generation_config - Настройка моделей для генерации изображений\n"
                "/context - Управление контекстом (запоминание предыдущих сообщений)\n"
                "/web_search - Управление веб-поиском\n"
                "/help - Вывод этой справки\n\n"
                "Вы также можете просто написать мне, что вы хотите, и я автоматически определю "
                "ваше намерение (чат, поиск или генерация изображений).",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке команды help: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

    # ==================== ОБРАБОТЧИКИ КОЛБЭКОВ ====================

    @dp.callback_query()
    async def handle_callback_query(callback: CallbackQuery):
        """Обработка всех callback-запросов от инлайн клавиатуры"""
        try:
            user = await get_or_create_user(callback.message)
            chat = await get_or_create_chat(user)

            # Парсим данные callback
            try:
                data = json.loads(callback.data)
                action = data.get("action")
            except:
                await callback.answer("Неверный формат данных")
                return

            # Обработка разных типов действий
            if action == "cancel":
                # Просто закрываем инлайн-клавиатуру и отвечаем
                await callback.message.delete_reply_markup()
                await callback.answer("Операция отменена")

            elif action == "select_chat_model":
                model_id = data.get("model_id")
                is_allowed = data.get("allowed", False)

                if not is_allowed:
                    await callback.answer("Эта модель недоступна")
                    return

                # Сохраняем выбранную модель и создаем новый чат
                user.gpt_model = model_id
                chat.bothub_chat_model = model_id
                chat.reset_context_counter()

                await user_repository.update(user)

                # Создаем новый чат с выбранной моделью
                await chat_session_usecase.gateway.create_new_chat(user, chat)
                await chat_repository.update(chat)

                # Обновляем сообщение и отвечаем пользователю
                await callback.message.delete_reply_markup()
                await callback.answer(f"Модель {model_id} выбрана")
                await callback.message.answer(
                    f"✅ Модель *{model_id}* успешно выбрана и новый чат создан.",
                    parse_mode="Markdown"
                )

            elif action == "select_image_model":
                model_id = data.get("model_id")
                is_allowed = data.get("allowed", False)

                if not is_allowed:
                    await callback.answer("Эта модель недоступна")
                    return

                # Сохраняем выбранную модель
                user.image_generation_model = model_id
                await user_repository.update(user)

                # Обновляем сообщение и отвечаем пользователю
                await callback.message.delete_reply_markup()
                await callback.answer(f"Модель {model_id} выбрана для генерации изображений")
                await callback.message.answer(
                    f"✅ Модель *{model_id}* успешно выбрана для генерации изображений.",
                    parse_mode="Markdown"
                )

            elif action == "toggle_web_search":
                # Получаем текущий статус и переключаем его
                current_status = await web_search_usecase.gateway.get_web_search(user, chat)
                new_status = not current_status

                # Применяем новый статус
                await web_search_usecase.toggle_web_search(user, chat, new_status)

                # Обновляем клавиатуру
                await callback.message.edit_reply_markup(
                    reply_markup=get_web_search_inline_keyboard(new_status)
                )

                status_text = "включен" if new_status else "выключен"
                await callback.answer(f"Веб-поиск {status_text}")

            elif action == "context_on":
                # Включаем контекст
                chat.context_remember = True
                chat.reset_context_counter()
                await chat_repository.update(chat)

                # Создаем новый чат с активным контекстом
                await chat_session_usecase.gateway.create_new_chat(user, chat)

                # Обновляем сообщение и отвечаем пользователю
                await callback.message.delete_reply_markup()
                await callback.answer("Контекст включен")
                await callback.message.answer(
                    "✅ Контекст включен. Теперь я буду помнить предыдущие сообщения.",
                    parse_mode="Markdown"
                )

            elif action == "context_off":
                # Выключаем контекст
                chat.context_remember = False
                chat.reset_context_counter()
                await chat_repository.update(chat)

                # Создаем новый чат с выключенным контекстом
                await chat_session_usecase.gateway.create_new_chat(user, chat)

                # Обновляем сообщение и отвечаем пользователю
                await callback.message.delete_reply_markup()
                await callback.answer("Контекст выключен")
                await callback.message.answer(
                    "✅ Контекст выключен. Теперь я не буду помнить предыдущие сообщения.",
                    parse_mode="Markdown"
                )

            elif action == "MJ_BUTTON":
                # Обработка кнопок Midjourney
                button_id = data.get("id")

                if not button_id:
                    await callback.answer("Некорректный ID кнопки")
                    return

                # Сообщаем о начале обработки
                await callback.answer("Обрабатываю запрос Midjourney...")
                await callback.message.answer("🎨 Обрабатываю ваш выбор, это может занять некоторое время...")

                # Вызываем метод для обработки кнопки Midjourney
                try:
                    # В этом месте должен быть соответствующий usecase для кнопок Midjourney
                    # Пока просто имитируем
                    result = await image_generation_usecase.generate_image(
                        user,
                        chat,
                        f"Применяю действие Midjourney (button_id: {button_id})"
                    )

                    # Обрабатываем результаты
                    if "attachments" in result.get("response", {}):
                        # Отправляем каждое сгенерированное изображение
                        for attachment in result["response"]["attachments"]:
                            if attachment.get("file", {}).get("type") == "IMAGE":
                                image_url = attachment["file"].get("url", "")
                                if not image_url and "path" in attachment["file"]:
                                    image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                if image_url:
                                    # Проверяем наличие кнопок Midjourney
                                    inline_markup = None
                                    if attachment.get("buttons") and any(
                                            btn.get("type") == "MJ_BUTTON" for btn in attachment["buttons"]):
                                        # Формируем кнопки для Midjourney
                                        mj_buttons = []
                                        for btn in attachment["buttons"]:
                                            if btn.get("type") == "MJ_BUTTON":
                                                mj_buttons.append(
                                                    InlineKeyboardButton(
                                                        text=btn.get("mj_native_label", "Действие"),
                                                        callback_data=json.dumps({
                                                            "action": "MJ_BUTTON",
                                                            "id": btn.get("id")
                                                        })
                                                    )
                                                )

                                        # Если есть кнопки, создаем инлайн-клавиатуру
                                        if mj_buttons:
                                            inline_markup = InlineKeyboardMarkup(inline_keyboard=[mj_buttons])

                                    # Отправляем изображение с кнопками или без
                                    await callback.message.answer_photo(
                                        photo=image_url,
                                        caption=result.get("response", {}).get("content", ""),
                                        reply_markup=inline_markup
                                    )
                    else:
                        # Если изображения не сгенерированы, отправляем текстовый ответ
                        content = result.get("response", {}).get("content", "Не удалось обработать кнопку")
                        await callback.message.answer(content, parse_mode="Markdown")

                except Exception as e:
                    logger.error(f"Ошибка при обработке кнопки Midjourney: {e}", exc_info=True)
                    await callback.message.answer(
                        "❌ Произошла ошибка при обработке кнопки Midjourney. Попробуйте еще раз.",
                        parse_mode="Markdown"
                    )

            else:
                await callback.answer("Неизвестное действие")

        except Exception as e:
            logger.error(f"Ошибка при обработке callback_query: {e}", exc_info=True)
            await callback.answer("Произошла ошибка при обработке запроса")

    # ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ С УМНЫМ ОПРЕДЕЛЕНИЕМ НАМЕРЕНИЙ ====================

    @dp.message(F.text)
    async def handle_text_message(message: Message):
        """Обработка текстовых сообщений с умным определением намерения"""
        try:
            # Сообщаем пользователю, что бот печатает
            await message.chat.do(ChatAction.TYPING)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Определяем намерение пользователя
            intent, intent_data = intent_detection_service.detect_intent(
                message.text,
                str(user.id),  # Используем ID пользователя для контекста
                None  # Пока не используем историю чата
            )

            # Обновляем контекст намерений пользователя
            intent_detection_service.update_user_context(str(user.id), intent, intent_data)

            # Обрабатываем разные типы намерений
            if intent == IntentType.WEB_SEARCH:
                # Отправляем сообщение о поиске
                await message.answer(
                    f"🔍 *Ищу информацию:* {intent_data.get('query')}",
                    parse_mode="Markdown"
                )

                # Выполняем веб-поиск
                response = await web_search_usecase.search(
                    user,
                    chat,
                    intent_data.get("query", message.text),
                    None  # Пока без файлов
                )

                # Отправляем результаты поиска
                content = response.get("response", {}).get("content", "Не удалось найти информацию")
                await send_long_message(message, content)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

            elif intent == IntentType.IMAGE_GENERATION:
                # Отправляем сообщение о генерации изображения
                await message.answer(
                    f"🎨 *Генерирую изображение:* {intent_data.get('prompt')}",
                    parse_mode="Markdown"
                )

                # Меняем статус на загрузку фото вместо печатания
                await message.chat.do(ChatAction.UPLOAD_PHOTO)

                # Выполняем генерацию изображения
                response = await image_generation_usecase.generate_image(
                    user,
                    chat,
                    intent_data.get("prompt", message.text),
                    None  # Пока без файлов
                )

                # Обрабатываем результаты
                if "attachments" in response.get("response", {}):
                    # Отправляем каждое сгенерированное изображение
                    for attachment in response["response"]["attachments"]:
                        if attachment.get("file", {}).get("type") == "IMAGE":
                            image_url = attachment["file"].get("url", "")
                            if not image_url and "path" in attachment["file"]:
                                image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                            if image_url:
                                # Проверяем наличие кнопок Midjourney
                                inline_markup = None
                                if attachment.get("buttons") and any(
                                        btn.get("type") == "MJ_BUTTON" for btn in attachment["buttons"]):
                                    # Формируем кнопки для Midjourney
                                    mj_buttons = []
                                    for btn in attachment["buttons"]:
                                        if btn.get("type") == "MJ_BUTTON":
                                            mj_buttons.append(
                                                InlineKeyboardButton(
                                                    text=btn.get("mj_native_label", "Действие"),
                                                    callback_data=json.dumps({
                                                        "action": "MJ_BUTTON",
                                                        "id": btn.get("id")
                                                    })
                                                )
                                            )

                                    # Если есть кнопки, создаем инлайн-клавиатуру
                                    if mj_buttons:
                                        inline_markup = InlineKeyboardMarkup(inline_keyboard=[mj_buttons])

                                # Отправляем изображение с кнопками или без
                                await message.answer_photo(
                                    photo=image_url,
                                    caption=response.get("response", {}).get("content", ""),
                                    reply_markup=inline_markup
                                )
                else:
                    # Если изображения не сгенерированы, отправляем текстовый ответ
                    content = response.get("response", {}).get("content", "Не удалось сгенерировать изображение")
                    await message.answer(content, parse_mode="Markdown")

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

            else:  # IntentType.CHAT - обычный чат
                # Отправляем сообщение в нейросеть
                response = await chat_session_usecase.send_message(
                    user,
                    chat,
                    message.text,
                    None  # Пока без файлов
                )

                # Отправляем текстовый ответ
                content = response.get("response", {}).get("content", "Не удалось получить ответ")
                await send_long_message(message, content)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    if chat.context_remember:
                        caps_text += f"\n\nКонтекст: {chat.context_counter} сообщений"
                        # Информируем пользователя каждые 10 сообщений
                        if chat.context_counter > 0 and chat.context_counter % 10 == 0:
                            caps_text += "\n⚠️ Вы можете сбросить контекст командой /reset"

                    await message.answer(caps_text)

            # Сохраняем обновленные данные
            await user_repository.update(user)
            await chat_repository.update(chat)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке сообщения. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    # ==================== ОБРАБОТЧИК ГОЛОСОВЫХ СООБЩЕНИЙ ====================

    @dp.message(F.voice | F.audio)
    async def handle_voice_message(message: Message):
        """Обработка голосовых сообщений"""
        try:
            # Сообщаем пользователю, что бот печатает
            await message.chat.do(ChatAction.TYPING)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем файл
            file_id = message.voice.file_id if message.voice else message.audio.file_id

            # Отправляем сообщение о начале транскрибации
            await message.answer(
                "🎤 Транскрибирую голосовое сообщение...",
                parse_mode="Markdown"
            )

            try:
                # Получаем URL файла через Telegram API
                file_url = await message.bot.get_file_url(file_id)

                # Отправляем файл в BotHub для транскрибации
                # Здесь должен быть соответствующий код для транскрибации
                # Пока просто симулируем

                # Создаем временное сообщение с текстом голосового
                transcribed_text = "Это текст транскрибации голосового сообщения. В реальной имплементации здесь будет текст из голосового сообщения, полученный через API BotHub."

                # Определяем намерение пользователя на основе транскрибированного текста
                intent, intent_data = intent_detection_service.detect_intent(
                    transcribed_text,
                    str(user.id),
                    None
                )

                # Обновляем контекст намерений пользователя
                intent_detection_service.update_user_context(str(user.id), intent, intent_data)

                # Отправляем текст транскрибации
                await message.answer(
                    f"📝 *Транскрибация:* {transcribed_text}",
                    parse_mode="Markdown"
                )

                # Обрабатываем намерение так же, как и для текстовых сообщений
                if intent == IntentType.WEB_SEARCH:
                    await message.answer(
                        f"🔍 *Ищу информацию:* {intent_data.get('query')}",
                        parse_mode="Markdown"
                    )

                    response = await web_search_usecase.search(
                        user,
                        chat,
                        intent_data.get("query", transcribed_text),
                        None
                    )

                    content = response.get("response", {}).get("content", "Не удалось найти информацию")
                    await send_long_message(message, content)

                elif intent == IntentType.IMAGE_GENERATION:
                    await message.answer(
                        f"🎨 *Генерирую изображение:* {intent_data.get('prompt')}",
                        parse_mode="Markdown"
                    )

                    await message.chat.do(ChatAction.UPLOAD_PHOTO)

                    response = await image_generation_usecase.generate_image(
                        user,
                        chat,
                        intent_data.get("prompt", transcribed_text),
                        None
                    )

                    # Обработка результатов генерации изображения как в текстовом обработчике
                    if "attachments" in response.get("response", {}):
                        for attachment in response["response"]["attachments"]:
                            if attachment.get("file", {}).get("type") == "IMAGE":
                                image_url = attachment["file"].get("url", "")
                                if not image_url and "path" in attachment["file"]:
                                    image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                if image_url:
                                    # Проверяем наличие кнопок Midjourney
                                    inline_markup = None
                                    if attachment.get("buttons") and any(
                                            btn.get("type") == "MJ_BUTTON" for btn in attachment["buttons"]):
                                        # Формируем кнопки для Midjourney
                                        mj_buttons = []
                                        for btn in attachment["buttons"]:
                                            if btn.get("type") == "MJ_BUTTON":
                                                mj_buttons.append(
                                                    InlineKeyboardButton(
                                                        text=btn.get("mj_native_label", "Действие"),
                                                        callback_data=json.dumps({
                                                            "action": "MJ_BUTTON",
                                                            "id": btn.get("id")
                                                        })
                                                    )
                                                )

                                        # Если есть кнопки, создаем инлайн-клавиатуру
                                        if mj_buttons:
                                            inline_markup = InlineKeyboardMarkup(inline_keyboard=[mj_buttons])

                                    # Отправляем изображение с кнопками или без
                                    await message.answer_photo(
                                        photo=image_url,
                                        caption=response.get("response", {}).get("content", ""),
                                        reply_markup=inline_markup
                                    )
                    else:
                        content = response.get("response", {}).get("content", "Не удалось сгенерировать изображение")
                        await message.answer(content, parse_mode="Markdown")

                else:  # IntentType.CHAT
                    response = await chat_session_usecase.send_message(
                        user,
                        chat,
                        transcribed_text,
                        None
                    )

                    content = response.get("response", {}).get("content", "Не удалось получить ответ")
                    await send_long_message(message, content)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

            except Exception as voice_error:
                logger.error(f"Ошибка обработки голосового сообщения: {voice_error}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать голосовое сообщение. Пожалуйста, повторите позже или отправьте текстовое сообщение.",
                    parse_mode="Markdown"
                )

            # Сохраняем обновленные данные
            await user_repository.update(user)
            await chat_repository.update(chat)

        except Exception as e:
            logger.error(f"Ошибка обработки голосового сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке голосового сообщения.",
                parse_mode="Markdown"
            )

    # ==================== ОБРАБОТЧИК ИЗОБРАЖЕНИЙ ====================

    @dp.message(F.photo | F.document)
    async def handle_photo_document(message: Message):
        """Обработка фото и документов"""
        try:
            # Сообщаем пользователю, что бот печатает
            await message.chat.do(ChatAction.TYPING)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем файл и подпись (если есть)
            file_id = None
            caption = message.caption or ""

            if message.photo:
                # Берем самую большую версию фото
                file_id = message.photo[-1].file_id
            elif message.document:
                file_id = message.document.file_id

            if not file_id:
                await message.answer(
                    "❌ Не удалось получить файл. Пожалуйста, попробуйте еще раз.",
                    parse_mode="Markdown"
                )
                return

            # Получаем URL файла через Telegram API
            file_url = await message.bot.get_file_url(file_id)

            # Определяем намерение пользователя по подписи
            if caption:
                intent, intent_data = intent_detection_service.detect_intent(
                    caption,
                    str(user.id),
                    None
                )

                # Обновляем контекст намерений пользователя
                intent_detection_service.update_user_context(str(user.id), intent, intent_data)

                # Если у нас есть определенное намерение в подписи, обрабатываем его
                if intent == IntentType.WEB_SEARCH:
                    await message.answer(
                        f"🔍 *Ищу информацию по изображению и запросу:* {intent_data.get('query')}",
                        parse_mode="Markdown"
                    )

                    # Отправляем файл в BotHub для поиска по изображению и запросу
                    response = await web_search_usecase.search(
                        user,
                        chat,
                        intent_data.get("query", caption),
                        [file_url]  # Передаем URL файла
                    )

                    content = response.get("response", {}).get("content", "Не удалось найти информацию")
                    await send_long_message(message, content)

                elif intent == IntentType.IMAGE_GENERATION:
                    await message.answer(
                        f"🎨 *Редактирую изображение:* {intent_data.get('prompt')}",
                        parse_mode="Markdown"
                    )

                    await message.chat.do(ChatAction.UPLOAD_PHOTO)

                    # Отправляем файл в BotHub для редактирования изображения
                    response = await image_generation_usecase.generate_image(
                        user,
                        chat,
                        intent_data.get("prompt", caption),
                        [file_url]  # Передаем URL файла
                    )

                    # Обработка результатов как в других обработчиках
                    if "attachments" in response.get("response", {}):
                        for attachment in response["response"]["attachments"]:
                            if attachment.get("file", {}).get("type") == "IMAGE":
                                image_url = attachment["file"].get("url", "")
                                if not image_url and "path" in attachment["file"]:
                                    image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                if image_url:
                                    await message.answer_photo(
                                        photo=image_url,
                                        caption=response.get("response", {}).get("content", "")
                                    )
                    else:
                        content = response.get("response", {}).get("content", "Не удалось отредактировать изображение")
                        await message.answer(content, parse_mode="Markdown")

                else:  # IntentType.CHAT
                    # Просто отправляем изображение в чат с нейросетью
                    response = await chat_session_usecase.send_message(
                        user,
                        chat,
                        caption,
                        [file_url]  # Передаем URL файла
                    )

                    content = response.get("response", {}).get("content", "Не удалось получить ответ")
                    await send_long_message(message, content)
            else:
                # Если нет подписи, просто анализируем изображение
                await message.answer(
                    "🔍 *Анализирую изображение...*",
                    parse_mode="Markdown"
                )

                # Отправляем изображение в чат с нейросетью для анализа
                response = await chat_session_usecase.send_message(
                    user,
                    chat,
                    "Опиши это изображение подробно",  # Запрос на описание изображения
                    [file_url]  # Передаем URL файла
                )

                content = response.get("response", {}).get("content", "Не удалось проанализировать изображение")
                await send_long_message(message, content)

            # Если есть счетчик капсов, добавляем его
            if "tokens" in response:
                caps_text = f"👾 -{response['tokens']} caps"
                await message.answer(caps_text)

            # Сохраняем обновленные данные
            await user_repository.update(user)
            await chat_repository.update(chat)

        except Exception as e:
            logger.error(f"Ошибка обработки фото/документа: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке изображения или документа.",
                parse_mode="Markdown"
            )

    # Возвращаем роутер для aiogram
    return dp