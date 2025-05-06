# src/delivery/telegram/handlers.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums.chat_action import ChatAction
from src.domain.service.intent_detection import IntentDetectionService, IntentType
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.account_connection import AccountConnectionUseCase
from src.domain.usecase.image_generation import ImageGenerationUseCase
from src.domain.usecase.web_search import WebSearchUseCase
from src.domain.usecase.system_prompt import SystemPromptUseCase
from src.domain.usecase.present import PresentUseCase
from src.domain.usecase.referral import ReferralUseCase
from src.domain.usecase.model_selection import ModelSelectionUseCase
from src.domain.usecase.buffer_message import BufferMessageUseCase
from src.domain.service.chat_service import ChatService
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
from src.adapter.repository.present_repository import PresentRepository
import logging
import json
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Создаём роутер для aiogram
#dp = Router()


def create_handlers(
        chat_session_usecase: ChatSessionUseCase,
        account_connection_usecase: AccountConnectionUseCase,
        intent_detection_service: IntentDetectionService,
        user_repository: UserRepository,
        chat_repository: ChatRepository,
        present_repository: PresentRepository = None,
        image_generation_usecase: Optional[ImageGenerationUseCase] = None,
        web_search_usecase: Optional[WebSearchUseCase] = None,
        system_prompt_usecase: Optional[SystemPromptUseCase] = None,
        present_usecase: Optional[PresentUseCase] = None,
        referral_usecase: Optional[ReferralUseCase] = None,
        model_selection_usecase: Optional[ModelSelectionUseCase] = None,
        buffer_message_usecase: Optional[BufferMessageUseCase] = None,
        chat_service: Optional[ChatService] = None
):
    logger.info("Starting create_handlers")
    router = Router()
    logger.info("Router created"
    """Фабричный метод для создания обработчиков сообщений Telegram""")

    # ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
    try:
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
                    current_chat_index=1,
                    current_chat_list_page=1
                )
                user_id = await user_repository.save(user)
                user.id = user_id

            return user

        async def get_or_create_chat(user: User) -> Chat:
            """Получение или создание чата для пользователя"""
            chat = await chat_repository.find_by_user_id_and_chat_index(user.id, user.current_chat_index)

            if not chat:
                chat = Chat(
                    id=0,
                    user_id=user.id,
                    chat_index=user.current_chat_index,
                    context_remember=True,
                    context_counter=0,
                    links_parse=False,
                    formula_to_image=False,
                    answer_to_voice=False
                )

                # Специальная настройка для пятого чата (📝)
                if user.current_chat_index == 5:
                    chat.context_remember = False
                    chat.system_prompt = "Ты помощник, который помогает писать и редактировать тексты."

                chat_id = await chat_repository.save(chat)
                chat.id = chat_id

            return chat

        async def send_long_message(message: Message, content: str, parse_mode: str = "Markdown"):
            """Отправляет длинное сообщение, разбивая его на части, если необходимо."""
            max_length = 3900 if parse_mode == "Markdown" else 4096

            if len(content) <= max_length:
                await message.answer(content, parse_mode=parse_mode)
                return

            parts = []
            while content:
                if len(content) <= max_length:
                    parts.append(content)
                    content = ""
                else:
                    last_newline = content[:max_length].rfind("\n")
                    if last_newline == -1:
                        last_newline = max_length
                    parts.append(content[:last_newline])
                    content = content[last_newline:]

            for part in parts:
                await message.answer(part, parse_mode=parse_mode)

        # ==================== ГЕНЕРАТОРЫ КЛАВИАТУР ====================

        def get_main_keyboard(user: User, chat: Chat) -> ReplyKeyboardMarkup:
            """Создание основной клавиатуры бота"""
            chat_buttons = get_chat_buttons(user.current_chat_index)

            web_search_text = "🔍 Поиск в интернете"
            if hasattr(chat, 'web_search_enabled') and chat.web_search_enabled:
                web_search_text += " ✅"
            else:
                web_search_text += " ❌"

            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="🔄 Новый чат"),
                        KeyboardButton(text=web_search_text),
                        KeyboardButton(text="🎨 Генерация изображений")
                    ],
                    [
                        KeyboardButton(text="⚙️ Инструменты"),
                        KeyboardButton(text="📋 Буфер")
                    ] + chat_buttons
                ],
                resize_keyboard=True
            )

            return keyboard

        def get_chat_buttons(current_chat_index: int) -> List[KeyboardButton]:
            """Возвращает кнопки чатов с маркером текущего чата"""
            buttons = []
            chat_emojis = {"1️⃣": 1, "2️⃣": 2, "3️⃣": 3, "4️⃣": 4, "📝": 5}

            for emoji, index in chat_emojis.items():
                if index == current_chat_index:
                    buttons.append(KeyboardButton(text=f"{emoji}✅"))
                else:
                    buttons.append(KeyboardButton(text=emoji))

            return buttons

        def get_buffer_keyboard() -> ReplyKeyboardMarkup:
            """Клавиатура для режима буфера"""
            return ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text="📤 Отправить буфер"),
                        KeyboardButton(text="❌ Отмена")
                    ]
                ],
                resize_keyboard=True
            )

        def get_chat_model_inline_keyboard(models: List[Dict], current_model: Optional[str] = None) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для выбора модели чата"""
            buttons = []

            # Фильтруем только модели для текстовой генерации
            if model_selection_usecase:
                text_models = model_selection_usecase.filter_text_models(models)
            else:
                # Если юзкейс не предоставлен, используем все модели
                text_models = models

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
            if model_selection_usecase:
                image_models = model_selection_usecase.filter_image_models(models)
            else:
                # Если юзкейс не предоставлен, используем все модели
                image_models = models

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

        def get_chat_list_inline_keyboard(chats: List[Chat], current_chat_index: int,
                                          page: int, total_pages: int) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для просмотра списка чатов"""
            buttons = []

            # Добавляем чаты на текущей странице
            for chat in chats:
                text = f"Чат {chat.chat_index}"
                if chat.name:
                    text += f" | {chat.name}"
                if chat.chat_index == current_chat_index:
                    text += " ✅"

                callback_data = json.dumps({
                    "action": "select_chat",
                    "chat_index": chat.chat_index,
                    "current_page": page
                })

                buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

            # Добавляем навигационные кнопки
            nav_buttons = []

            if page > 1:
                nav_buttons.append(InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=json.dumps({"action": "chat_page", "page": page - 1})
                ))

            nav_buttons.append(InlineKeyboardButton(
                text=f"{page}/{total_pages}",
                callback_data=json.dumps({"action": "current_page"})
            ))

            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton(
                    text="Вперёд ▶️",
                    callback_data=json.dumps({"action": "chat_page", "page": page + 1})
                ))

            if nav_buttons:
                buttons.append(nav_buttons)

            # Добавляем кнопку создания нового чата
            buttons.append([InlineKeyboardButton(
                text="➕ Создать новый чат",
                callback_data=json.dumps({"action": "create_new_chat"})
            )])

            # Добавляем кнопку отмены
            buttons.append([InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=json.dumps({"action": "cancel"})
            )])

            return InlineKeyboardMarkup(inline_keyboard=buttons)

        def get_referral_templates_inline_keyboard(templates: List[Any]) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для выбора шаблона реферальной программы"""
            buttons = []

            for template in templates:
                text = f"{template.name} | {template.tokens} токенов"
                callback_data = json.dumps({
                    "action": "select_referral_template",
                    "template_id": template.id
                })

                buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

            # Добавляем кнопку отмены
            buttons.append([InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=json.dumps({"action": "cancel"})
            )])

            return InlineKeyboardMarkup(inline_keyboard=buttons)

        def get_formula_image_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для управления конвертацией формул в изображения"""
            buttons = [
                [InlineKeyboardButton(
                    text=f"Конвертировать формулы в изображения {'✅' if enabled else ''}",
                    callback_data=json.dumps({"action": "formula_to_image_on"})
                )],
                [InlineKeyboardButton(
                    text=f"Не конвертировать формулы {'✅' if not enabled else ''}",
                    callback_data=json.dumps({"action": "formula_to_image_off"})
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=json.dumps({"action": "cancel"})
                )]
            ]
            return InlineKeyboardMarkup(inline_keyboard=buttons)

        def get_links_parse_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для управления парсингом ссылок"""
            buttons = [
                [InlineKeyboardButton(
                    text=f"Парсить ссылки {'✅' if enabled else ''}",
                    callback_data=json.dumps({"action": "links_parse_on"})
                )],
                [InlineKeyboardButton(
                    text=f"Не парсить ссылки {'✅' if not enabled else ''}",
                    callback_data=json.dumps({"action": "links_parse_off"})
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=json.dumps({"action": "cancel"})
                )]
            ]
            return InlineKeyboardMarkup(inline_keyboard=buttons)

        def get_voice_answer_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
            """Возвращает инлайн-клавиатуру для управления ответами голосом"""
            buttons = [
                [InlineKeyboardButton(
                    text=f"Отвечать голосом {'✅' if enabled else ''}",
                    callback_data=json.dumps({"action": "voice_answer_on"})
                )],
                [InlineKeyboardButton(
                    text=f"Не отвечать голосом {'✅' if not enabled else ''}",
                    callback_data=json.dumps({"action": "voice_answer_off"})
                )],
                [InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=json.dumps({"action": "cancel"})
                )]
            ]
            return InlineKeyboardMarkup(inline_keyboard=buttons)

        # ==================== ОБРАБОТЧИКИ КОМАНД ====================

        @router.message(Command("start"))
        async def handle_start_command(message: Message):
            """Обработка команды /start"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                # Проверяем наличие реферального кода
                if message.text and len(message.text.split()) > 1:
                    user.referral_code = message.text.split()[1]
                    await user_repository.update(user)

                # Отправляем уведомления о подарках, если есть
                if present_usecase:
                    await present_usecase.send_notifications(user)

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
                    "/web_search - управление веб-поиском\n"
                    "/system_prompt - настройка системного промпта\n"
                    "/link_account - привязать аккаунт к существующему аккаунту BotHub\n"
                    "/referral - управление реферальной программой\n"
                    "/present - подарить токены другому пользователю",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
            except Exception as e:
                logger.error(f"Ошибка обработки команды /start: {e}", exc_info=True)
                await message.answer(
                    "❌ Извините, произошла ошибка при обработке команды",
                    parse_mode="Markdown"
                )

        @router.message(Command("reset"))
        async def handle_reset_command(message: Message):
            """Обработка команды /reset для сброса контекста"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                # Сбрасываем контекст
                await chat_session_usecase.reset_context(user, chat)
                chat.reset_context_counter()
                await chat_repository.update(chat)

                await message.answer(
                    "🔄 Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
            except Exception as e:
                logger.error(f"Ошибка сброса контекста: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
                    parse_mode="Markdown"
                )

        @router.message(Command("link_account"))
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

                    # Отправляем сообщение с ссылкой
                    await message.answer(
                        f"Для привязки вашего Telegram к существующему аккаунту BotHub, перейдите по ссылке:\n\n{link}\n\n"
                        f"После привязки вы сможете использовать ваши токены из аккаунта BotHub."
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

        @router.message(Command("gpt_config"))
        async def handle_gpt_config_command(message: Message):
            """Обработка команды /gpt_config для настройки моделей"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                if not model_selection_usecase:
                    await message.answer(
                        "❌ Настройка моделей временно недоступна.",
                        parse_mode="Markdown"
                    )
                    return

                # Получаем список доступных моделей
                models = await model_selection_usecase.list_available_models(user)

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

        @router.message(Command("image_generation_config"))
        async def handle_image_generation_config_command(message: Message):
            """Обработка команды /image_generation_config для настройки моделей генерации изображений"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                if not model_selection_usecase:
                    await message.answer(
                        "❌ Настройка моделей временно недоступна.",
                        parse_mode="Markdown"
                    )
                    return

                # Получаем список доступных моделей
                models = await model_selection_usecase.list_available_models(user)

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

        @router.message(Command("context"))
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

        @router.message(Command("web_search"))
        async def handle_web_search_command(message: Message):
            """Обработка команды /web_search для управления веб-поиском"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                if not web_search_usecase:
                    await message.answer(
                        "❌ Управление веб-поиском временно недоступно.",
                        parse_mode="Markdown"
                    )
                    return

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

        @router.message(Command("system_prompt"))
        async def handle_system_prompt_command(message: Message):
            """Обработка команды /system_prompt для управления системным промптом"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                if not system_prompt_usecase:
                    await message.answer(
                        "❌ Управление системным промптом временно недоступно.",
                        parse_mode="Markdown"
                    )
                    return

                # Проверяем, есть ли у сообщения текст после команды
                command_text = message.text.strip()
                parts = command_text.split(maxsplit=1)

                if len(parts) > 1:
                    # Если есть текст после команды, устанавливаем его как системный промпт
                    new_prompt = parts[1]

                    # Обрабатываем команду сброса
                    if new_prompt.lower() == "reset":
                        await system_prompt_usecase.reset_system_prompt(user, chat)
                        await message.answer(
                            "✅ Системный промпт сброшен.",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, chat)
                        )
                        return

                    # Устанавливаем новый промпт
                    await system_prompt_usecase.set_system_prompt(user, chat, new_prompt)
                    await message.answer(
                        f"✅ Системный промпт установлен:\n\n{new_prompt}",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )
                else:
                    # Если нет текста, показываем текущий промпт и предлагаем его изменить
                    current_prompt = await system_prompt_usecase.get_system_prompt(chat)

                    if current_prompt:
                        await message.answer(
                            f"📝 Текущий системный промпт:\n\n{current_prompt}\n\n"
                            f"Чтобы изменить системный промпт, отправьте команду `/system_prompt новый промпт`\n\n"
                            f"Для сброса системного промпта отправьте `/system_prompt reset`",
                            parse_mode="Markdown"
                        )
                    else:
                        await message.answer(
                            "📝 Системный промпт не установлен.\n\n"
                            "Системный промпт позволяет задать поведение нейросети. "
                            "Чтобы установить системный промпт, отправьте команду `/system_prompt текст промпта`",
                            parse_mode="Markdown"
                        )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды system_prompt: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("formula"))
        async def handle_formula_command(message: Message):
            """Обработка команды /formula для управления конвертацией формул в изображения"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                await message.answer(
                    "Управление конвертацией формул в изображения:\n\n"
                    "Эта функция позволяет конвертировать математические формулы в изображения для лучшего отображения.",
                    parse_mode="Markdown",
                    reply_markup=get_formula_image_inline_keyboard(chat.formula_to_image)
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды formula: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("scan_links"))
        async def handle_scan_links_command(message: Message):
            """Обработка команды /scan_links для управления парсингом ссылок"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                await message.answer(
                    "Управление парсингом ссылок:\n\n"
                    "Эта функция позволяет боту автоматически сканировать и анализировать ссылки в ваших сообщениях.",
                    parse_mode="Markdown",
                    reply_markup=get_links_parse_inline_keyboard(chat.links_parse)
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды scan_links: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("voice"))
        async def handle_voice_command(message: Message):
            """Обработка команды /voice для управления ответами голосом"""
            try:
                user = await get_or_create_user(message)
                chat = await get_or_create_chat(user)

                await message.answer(
                    "Управление ответами голосом:\n\n"
                    "Эта функция позволяет боту отправлять ответы в виде голосовых сообщений.",
                    parse_mode="Markdown",
                    reply_markup=get_voice_answer_inline_keyboard(chat.answer_to_voice)
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды voice: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("present"))
        async def handle_present_command(message: Message):
            """Обработка команды /present для подарка токенов"""
            try:
                user = await get_or_create_user(message)

                if not present_usecase:
                    await message.answer(
                        "❌ Функция подарков токенов временно недоступна.",
                        parse_mode="Markdown"
                    )
                    return

                # Проверяем, есть ли у сообщения текст после команды
                command_text = message.text.strip()
                parts = command_text.split(maxsplit=2)

                if len(parts) > 2:
                    # Формат: /present username|email количество
                    recipient = parts[1]
                    try:
                        tokens = int(parts[2])
                    except ValueError:
                        await message.answer(
                            "❌ Неверный формат количества токенов. Используйте целое число.",
                            parse_mode="Markdown"
                        )
                        return

                    # Проверяем корректность получателя
                    is_valid, formatted_recipient = await present_usecase.verify_present_format(recipient)

                    if not is_valid:
                        await message.answer(
                            f"❌ {formatted_recipient}",
                            parse_mode="Markdown"
                        )
                        return

                    # Отправляем подарок
                    result = await present_usecase.send_present(user, formatted_recipient, tokens)

                    if result["success"]:
                        await message.answer(
                            f"✅ Подарок отправлен!\n\n"
                            f"Получатель: {formatted_recipient}\n"
                            f"Количество токенов: {tokens}",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, await get_or_create_chat(user))
                        )
                    else:
                        await message.answer(
                            f"❌ Не удалось отправить подарок: {result.get('error', 'Неизвестная ошибка')}",
                            parse_mode="Markdown"
                        )
                else:
                    # Показываем инструкцию по использованию команды
                    await message.answer(
                        "🎁 Подарить токены другому пользователю\n\n"
                        "Формат команды:\n"
                        "`/present получатель количество`\n\n"
                        "Получатель может быть:\n"
                        "- Email-адресом (например, user@example.com)\n"
                        "- Именем пользователя в Telegram (например, @username)\n\n"
                        "Пример: `/present @friend 100`",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды present: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("referral"))
        async def handle_referral_command(message: Message):
            """Обработка команды /referral для управления реферальной программой"""
            try:
                user = await get_or_create_user(message)

                if not referral_usecase:
                    await message.answer(
                        "❌ Функция реферальной программы временно недоступна.",
                        parse_mode="Markdown"
                    )
                    return

                # Проверяем, есть ли аргументы у команды
                command_text = message.text.strip()
                parts = command_text.split(maxsplit=1)

                if len(parts) > 1 and parts[1] == "new":
                    # Получаем шаблоны реферальных программ
                    templates = await referral_usecase.list_referral_templates(user)

                    if not templates:
                        await message.answer(
                            "❌ Не найдено доступных шаблонов реферальных программ.",
                            parse_mode="Markdown"
                        )
                        return

                    # Показываем список шаблонов для выбора
                    await message.answer(
                        "🔄 Создание новой реферальной программы\n\n"
                        "Выберите шаблон программы:",
                        parse_mode="Markdown",
                        reply_markup=get_referral_templates_inline_keyboard(templates)
                    )
                else:
                    # Получаем список реферальных программ пользователя
                    programs = await referral_usecase.list_referral_programs(user)

                    if not programs:
                        await message.answer(
                            "🔄 У вас пока нет реферальных программ.\n\n"
                            "Чтобы создать новую программу, используйте команду `/referral new`",
                            parse_mode="Markdown"
                        )
                        return

                    # Показываем список программ
                    first_message = True
                    for program in programs:
                        if first_message:
                            await message.answer(
                                "🔄 Ваши реферальные программы:",
                                parse_mode="Markdown"
                            )
                            first_message = False

                        # Получаем ссылки программы
                        links = referral_usecase.get_referral_links(program)

                        # Формируем сообщение с информацией о программе
                        program_text = (
                            f"📊 *{program.template.name if program.template else 'Реферальная программа'}*\n\n"
                            f"Код приглашения: `{links['code']}`\n"
                            f"Количество участников: {program.participants}\n"
                            f"Баланс: {program.balance} {program.template.currency if program.template else ''}\n\n"
                            f"Ссылки для приглашения:\n"
                            f"🌐 [Веб-ссылка]({links['web']})\n"
                            f"📱 [Telegram]({links['telegram']})"
                        )

                        await message.answer(
                            program_text,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды referral: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("chat_list"))
        async def handle_chat_list_command(message: Message):
            """Обработка команды /chat_list для просмотра списка чатов"""
            try:
                user = await get_or_create_user(message)

                if not chat_service:
                    await message.answer(
                        "❌ Функция просмотра списка чатов временно недоступна.",
                        parse_mode="Markdown"
                    )
                    return

                # Получаем список чатов с пагинацией
                chats, total_pages = await chat_service.get_chat_list(user, user.current_chat_list_page)

                await message.answer(
                    "📋 Список ваших чатов:",
                    parse_mode="Markdown",
                    reply_markup=get_chat_list_inline_keyboard(chats, user.current_chat_index,
                                                               user.current_chat_list_page, total_pages)
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке команды chat_list: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать команду. Попробуйте позже.",
                    parse_mode="Markdown"
                )

        @router.message(Command("help"))
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
                    "/system_prompt - Управление системным промптом\n"
                    "/formula - Управление конвертацией формул в изображения\n"
                    "/scan_links - Управление парсингом ссылок\n"
                    "/voice - Управление ответами голосом\n"
                    "/present - Подарить токены другому пользователю\n"
                    "/referral - Управление реферальной программой\n"
                    "/chat_list - Просмотр списка чатов\n"
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

        @router.callback_query()
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
                    if not model_selection_usecase:
                        await callback.answer("Функция недоступна")
                        return

                    model_id = data.get("model_id")
                    is_allowed = data.get("allowed", False)

                    if not is_allowed:
                        await callback.answer("Эта модель недоступна")
                        return

                    # Сохраняем выбранную модель и создаем новый чат
                    await model_selection_usecase.select_chat_model(user, chat, model_id)
                    await user_repository.update(user)
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer(f"Модель {model_id} выбрана")
                    await callback.message.answer(
                        f"✅ Модель *{model_id}* успешно выбрана и новый чат создан.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "select_image_model":
                    if not model_selection_usecase:
                        await callback.answer("Функция недоступна")
                        return

                    model_id = data.get("model_id")
                    is_allowed = data.get("allowed", False)

                    if not is_allowed:
                        await callback.answer("Эта модель недоступна")
                        return

                    # Сохраняем выбранную модель
                    await model_selection_usecase.select_image_model(user, model_id)
                    await user_repository.update(user)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer(f"Модель {model_id} выбрана для генерации изображений")
                    await callback.message.answer(
                        f"✅ Модель *{model_id}* успешно выбрана для генерации изображений.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "toggle_web_search":
                    if not web_search_usecase:
                        await callback.answer("Функция недоступна")
                        return

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
                    await chat_repository.update(chat)

                    # Создаем новый чат с активным контекстом
                    await chat_session_usecase.gateway.create_new_chat(user, chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Контекст включен")
                    await callback.message.answer(
                        "✅ Контекст включен. Теперь я буду помнить предыдущие сообщения.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
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
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "formula_to_image_on":
                    # Включаем конвертацию формул в изображения
                    chat.formula_to_image = True
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Конвертация формул включена")
                    await callback.message.answer(
                        "✅ Конвертация формул в изображения включена.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "formula_to_image_off":
                    # Выключаем конвертацию формул в изображения
                    chat.formula_to_image = False
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Конвертация формул выключена")
                    await callback.message.answer(
                        "✅ Конвертация формул в изображения выключена.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "links_parse_on":
                    # Включаем парсинг ссылок
                    chat.links_parse = True
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Парсинг ссылок включен")
                    await callback.message.answer(
                        "✅ Парсинг ссылок включен.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "links_parse_off":
                    # Выключаем парсинг ссылок
                    chat.links_parse = False
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Парсинг ссылок выключен")
                    await callback.message.answer(
                        "✅ Парсинг ссылок выключен.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "voice_answer_on":
                    # Включаем ответы голосом
                    chat.answer_to_voice = True
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Ответы голосом включены")
                    await callback.message.answer(
                        "✅ Ответы голосом включены.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "voice_answer_off":
                    # Выключаем ответы голосом
                    chat.answer_to_voice = False
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Ответы голосом выключены")
                    await callback.message.answer(
                        "✅ Ответы голосом выключены.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                elif action == "chat_page":
                    if not chat_service:
                        await callback.answer("Функция недоступна")
                        return

                    # Переключаем страницу чатов
                    page = data.get("page", 1)
                    user.current_chat_list_page = page
                    await user_repository.update(user)

                    # Получаем обновленный список чатов
                    chats, total_pages = await chat_service.get_chat_list(user, page)

                    # Обновляем клавиатуру
                    await callback.message.edit_reply_markup(
                        reply_markup=get_chat_list_inline_keyboard(chats, user.current_chat_index, page, total_pages)
                    )

                    await callback.answer(f"Страница {page}")

                elif action == "select_chat":
                    if not chat_service:
                        await callback.answer("Функция недоступна")
                        return

                    # Переключаемся на выбранный чат
                    chat_index = data.get("chat_index")
                    current_page = data.get("current_page", 1)

                    # Переключаем чат
                    selected_chat = await chat_service.switch_chat(user, chat_index)

                    if selected_chat:
                        await user_repository.update(user)

                        # Обновляем клавиатуру
                        chats, total_pages = await chat_service.get_chat_list(user, current_page)
                        await callback.message.edit_reply_markup(
                            reply_markup=get_chat_list_inline_keyboard(chats, user.current_chat_index, current_page,
                                                                       total_pages)
                        )

                        await callback.answer(f"Выбран чат {chat_index}")
                        await callback.message.answer(
                            f"✅ Выбран чат {chat_index}" + (f" | {selected_chat.name}" if selected_chat.name else ""),
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, selected_chat)
                        )
                    else:
                        await callback.answer("Чат не найден")

                elif action == "create_new_chat":
                    if not chat_service:
                        await callback.answer("Функция недоступна")
                        return

                    # Запрашиваем имя для нового чата
                    await callback.message.delete_reply_markup()
                    await callback.answer("Создание нового чата")

                    # Устанавливаем состояние пользователя
                    user.state = "waiting_for_chat_name"
                    await user_repository.update(user)

                    await callback.message.answer(
                        "📝 Введите название для нового чата или отправьте `/cancel` для отмены:",
                        parse_mode="Markdown"
                    )

                elif action == "select_referral_template":
                    if not referral_usecase:
                        await callback.answer("Функция недоступна")
                        return

                    # Создаем реферальную программу с выбранным шаблоном
                    template_id = data.get("template_id")

                    # Создаем программу
                    try:
                        program = await referral_usecase.create_referral_program(user, template_id)

                        # Получаем ссылки программы
                        links = referral_usecase.get_referral_links(program)

                        # Формируем сообщение с информацией о программе
                        program_text = (
                            f"✅ Реферальная программа успешно создана!\n\n"
                            f"📊 *{program.template.name if program.template else 'Реферальная программа'}*\n\n"
                            f"Код приглашения: `{links['code']}`\n\n"
                            f"Ссылки для приглашения:\n"
                            f"🌐 [Веб-ссылка]({links['web']})\n"
                            f"📱 [Telegram]({links['telegram']})"
                        )

                        await callback.message.delete_reply_markup()
                        await callback.message.answer(
                            program_text,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                            reply_markup=get_main_keyboard(user, chat)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при создании реферальной программы: {e}", exc_info=True)
                        await callback.message.delete_reply_markup()
                        await callback.message.answer(
                            f"❌ Не удалось создать реферальную программу: {str(e)}",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, chat)
                        )

                elif action == "MJ_BUTTON":
                    if not image_generation_usecase:
                        await callback.answer("Функция недоступна")
                        return

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
                        if "response" in result and "attachments" in result["response"]:
                            # Отправляем каждое сгенерированное изображение
                            for attachment in result["response"]["attachments"]:
                                if "file" in attachment and attachment["file"].get("type") == "IMAGE":
                                    image_url = attachment["file"].get("url", "")
                                    if not image_url and "path" in attachment["file"]:
                                        image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                    if image_url:
                                        # Проверяем наличие кнопок Midjourney
                                        inline_markup = None
                                        if "buttons" in attachment and any(
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
                                            caption=result["response"].get("content", ""),
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

                @router.message(F.text)
                async def handle_text_message(message: Message):
                    """Обработка текстовых сообщений с умным определением намерения"""
                    try:
                        # Получаем или создаём пользователя и его текущий чат
                        user = await get_or_create_user(message)

                        # Проверяем, находится ли пользователь в каком-то состоянии
                        if user.state == "waiting_for_chat_name":
                            # Пользователь вводит имя для нового чата
                            if message.text.startswith("/cancel"):
                                user.state = None
                                await user_repository.update(user)
                                await message.answer(
                                    "❌ Создание нового чата отменено.",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, await get_or_create_chat(user))
                                )
                                return

                            # Создаем новый чат с указанным именем
                            chat_name = message.text.strip()
                            if len(chat_name) > 50:  # Ограничиваем длину имени чата
                                await message.answer(
                                    "❌ Слишком длинное название чата. Максимальная длина - 50 символов.",
                                    parse_mode="Markdown"
                                )
                                return

                            # Создаем новый чат
                            if chat_service:
                                new_chat = await chat_service.create_new_chat(user, chat_name)
                                user.state = None
                                await user_repository.update(user)

                                await message.answer(
                                    f"✅ Создан новый чат: {chat_name}",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, new_chat)
                                )
                            return

                        # Проверяем, находится ли пользователь в режиме буфера
                        elif user.state == "buffer_mode":
                            if message.text.lower() in ["/cancel", "❌ отмена"]:
                                user.state = None
                                await user_repository.update(user)

                                # Очищаем буфер
                                chat = await get_or_create_chat(user)
                                if buffer_message_usecase:
                                    buffer_message_usecase.clear_buffer(chat)

                                await message.answer(
                                    "✅ Режим буфера отменен.",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, chat)
                                )
                                return

                            elif message.text.lower() in ["/send_buffer", "📤 отправить буфер"]:
                                # Отправляем содержимое буфера
                                user.state = None
                                await user_repository.update(user)

                                chat = await get_or_create_chat(user)
                                if buffer_message_usecase:
                                    try:
                                        # Отправляем буфер
                                        await message.chat.do(ChatAction.TYPING)
                                        result = await buffer_message_usecase.send_buffer(user, chat)

                                        # Обрабатываем ответ
                                        if "response" in result and "content" in result["response"]:
                                            await message.answer(
                                                result["response"]["content"],
                                                parse_mode="Markdown",
                                                reply_markup=get_main_keyboard(user, chat)
                                            )
                                        else:
                                            await message.answer(
                                                "✅ Буфер отправлен, но нет ответа от сервера.",
                                                parse_mode="Markdown",
                                                reply_markup=get_main_keyboard(user, chat)
                                            )
                                    except Exception as e:
                                        logger.error(f"Ошибка при отправке буфера: {e}", exc_info=True)
                                        await message.answer(
                                            f"❌ Ошибка при отправке буфера: {str(e)}",
                                            parse_mode="Markdown",
                                            reply_markup=get_main_keyboard(user, chat)
                                        )
                                return

                            # Добавляем сообщение в буфер
                            chat = await get_or_create_chat(user)
                            if buffer_message_usecase:
                                await buffer_message_usecase.add_to_buffer(user, chat, message.text)
                                await message.answer(
                                    "✅ Сообщение добавлено в буфер.",
                                    reply_markup=get_buffer_keyboard()
                                )
                            return

                        # Проверяем, не является ли сообщение командой клавиатуры
                        if message.text == "🔄 Новый чат":
                            # Создаем новый чат с текущей моделью
                            chat = await get_or_create_chat(user)
                            await chat_session_usecase.gateway.create_new_chat(user, chat)
                            chat.reset_context_counter()
                            await chat_repository.update(chat)

                            await message.answer(
                                f"✅ Создан новый чат с моделью {chat.bothub_chat_model or 'по умолчанию'}",
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )
                            return

                        elif message.text == "🎨 Генерация изображений":
                            # Запрашиваем промпт для генерации изображения
                            await message.answer(
                                "🎨 Введите описание изображения, которое хотите создать:",
                                parse_mode="Markdown"
                            )
                            return

                        elif message.text.startswith("🔍 Поиск в интернете"):
                            if not web_search_usecase:
                                await message.answer(
                                    "❌ Функция веб-поиска временно недоступна.",
                                    parse_mode="Markdown"
                                )
                                return

                            # Переключаем статус веб-поиска
                            chat = await get_or_create_chat(user)
                            current_status = await web_search_usecase.gateway.get_web_search(user, chat)
                            new_status = not current_status

                            await web_search_usecase.toggle_web_search(user, chat, new_status)

                            status_text = "включен" if new_status else "выключен"
                            await message.answer(
                                f"🔍 Веб-поиск {status_text}",
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )
                            return

                        elif message.text == "⚙️ Инструменты":
                            # Отображаем меню инструментов
                            await message.answer(
                                "⚙️ Инструменты:\n\n"
                                "/gpt_config - Настройка моделей для текста\n"
                                "/image_generation_config - Настройка моделей для изображений\n"
                                "/context - Управление контекстом\n"
                                "/web_search - Управление веб-поиском\n"
                                "/system_prompt - Управление системным промптом\n"
                                "/formula - Управление конвертацией формул\n"
                                "/scan_links - Управление парсингом ссылок\n"
                                "/voice - Управление ответами голосом\n"
                                "/chat_list - Просмотр списка чатов",
                                parse_mode="Markdown"
                            )
                            return

                        elif message.text == "📋 Буфер":
                            # Переходим в режим буфера
                            user.state = "buffer_mode"
                            await user_repository.update(user)

                            # Очищаем буфер
                            chat = await get_or_create_chat(user)
                            if buffer_message_usecase:
                                buffer_message_usecase.clear_buffer(chat)

                            await message.answer(
                                "📋 Режим буфера активирован.\n\n"
                                "Отправьте сообщения и файлы, которые нужно добавить в буфер.\n"
                                "Когда закончите, нажмите кнопку 'Отправить буфер'.\n"
                                "Для отмены нажмите 'Отмена'.",
                                parse_mode="Markdown",
                                reply_markup=get_buffer_keyboard()
                            )
                            return

                        # Проверяем, не является ли сообщение кнопкой чата
                        chat_emojis = {"1️⃣": 1, "2️⃣": 2, "3️⃣": 3, "4️⃣": 4, "📝": 5}
                        for emoji, index in chat_emojis.items():
                            if message.text.startswith(emoji):
                                # Переключаемся на выбранный чат
                                user.current_chat_index = index
                                await user_repository.update(user)

                                chat = await get_or_create_chat(user)

                                await message.answer(
                                    f"✅ Выбран чат {index}" + (f" | {chat.name}" if chat.name else ""),
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, chat)
                                )
                                return

                        # Сообщаем пользователю, что бот печатает
                        await message.chat.do(ChatAction.TYPING)

                        # Получаем текущий чат пользователя
                        chat = await get_or_create_chat(user)

                        # Определяем намерение пользователя
                        intent, intent_data = intent_detection_service.detect_intent(
                            message.text,
                            str(user.id),  # Используем ID пользователя для контекста
                            None  # Пока не используем историю чата
                        )

                        # Обновляем контекст намерений пользователя
                        intent_detection_service.update_user_context(str(user.id), intent, intent_data)

                        # Обрабатываем различные намерения
                        if intent == IntentType.IMAGE_GENERATION and image_generation_usecase:
                            # Генерация изображения
                            prompt = intent_data.get("prompt", message.text)

                            try:
                                result = await image_generation_usecase.generate_image(user, chat, prompt)

                                # Проверяем, есть ли вложения в ответе
                                if "response" in result and "attachments" in result["response"]:
                                    # Отправляем каждое сгенерированное изображение
                                    for attachment in result["response"]["attachments"]:
                                        if "file" in attachment and attachment["file"].get("type") == "IMAGE":
                                            image_url = attachment["file"].get("url", "")
                                            if not image_url and "path" in attachment["file"]:
                                                image_url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                            if image_url:
                                                # Проверяем наличие кнопок Midjourney
                                                inline_markup = None
                                                if "buttons" in attachment and any(
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
                                                    caption=result["response"].get("content", ""),
                                                    reply_markup=inline_markup
                                                )

                                # Если есть текстовый ответ, но нет изображений
                                elif "response" in result and "content" in result["response"] and result["response"][
                                    "content"]:
                                    await message.answer(
                                        result["response"]["content"],
                                        parse_mode="Markdown",
                                        reply_markup=get_main_keyboard(user, chat)
                                    )
                                else:
                                    await message.answer(
                                        "Не удалось сгенерировать изображение. Попробуйте изменить запрос.",
                                        parse_mode="Markdown",
                                        reply_markup=get_main_keyboard(user, chat)
                                    )
                            except Exception as e:
                                logger.error(f"Ошибка при генерации изображения: {e}", exc_info=True)
                                await message.answer(
                                    f"❌ Ошибка при генерации изображения: {str(e)}",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, chat)
                                )

                        elif intent == IntentType.WEB_SEARCH and web_search_usecase:
                            # Веб-поиск
                            query = intent_data.get("query", message.text)

                            try:
                                result = await web_search_usecase.search(user, chat, query)

                                if "response" in result and "content" in result["response"]:
                                    await message.answer(
                                        result["response"]["content"],
                                        parse_mode="Markdown",
                                        reply_markup=get_main_keyboard(user, chat)
                                    )
                                else:
                                    await message.answer(
                                        "Не удалось найти информацию по запросу. Попробуйте изменить запрос.",
                                        parse_mode="Markdown",
                                        reply_markup=get_main_keyboard(user, chat)
                                    )
                            except Exception as e:
                                logger.error(f"Ошибка при веб-поиске: {e}", exc_info=True)
                                await message.answer(
                                    f"❌ Ошибка при поиске информации: {str(e)}",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, chat)
                                )

                        else:
                            # Обычный чат
                            try:
                                result = await chat_session_usecase.send_message(user, chat, message.text)

                                if "response" in result and "content" in result["response"]:
                                    # Проверяем длину сообщения
                                    content = result["response"]["content"]
                                    if len(content) > 4000:
                                        # Разбиваем длинное сообщение на части
                                        await send_long_message(message, content)
                                    else:
                                        await message.answer(
                                            content,
                                            parse_mode="Markdown",
                                            reply_markup=get_main_keyboard(user, chat)
                                        )

                                    # Если есть информация о токенах, отправляем её
                                    if "tokens" in result:
                                        await message.answer(
                                            f"Использовано токенов: {result['tokens']}",
                                            parse_mode="Markdown"
                                        )
                                else:
                                    await message.answer(
                                        "Не удалось получить ответ от сервера.",
                                        parse_mode="Markdown",
                                        reply_markup=get_main_keyboard(user, chat)
                                    )
                            except Exception as e:
                                logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
                                await message.answer(
                                    f"❌ Ошибка при обработке сообщения: {str(e)}",
                                    parse_mode="Markdown",
                                    reply_markup=get_main_keyboard(user, chat)
                                )

                    except Exception as e:
                        logger.error(f"Общая ошибка при обработке текстового сообщения: {e}", exc_info=True)
                        await message.answer(
                            "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз.",
                            parse_mode="Markdown"
                        )

                # ==================== ОБРАБОТЧИКИ МЕДИА ФАЙЛОВ ====================

                @router.message(F.voice | F.audio)
                async def handle_voice_message(message: Message):
                    """Обработка голосовых сообщений"""
                    try:
                        user = await get_or_create_user(message)
                        chat = await get_or_create_chat(user)

                        # Проверяем режим буфера
                        if user.state == "buffer_mode" and buffer_message_usecase:
                            # Скачиваем файл
                            file_id = message.voice.file_id if message.voice else message.audio.file_id
                            file = await message.bot.get_file(file_id)
                            file_path = file.file_path
                            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                            # Добавляем в буфер
                            await buffer_message_usecase.add_to_buffer(
                                user,
                                chat,
                                None,  # Текст будет получен при распознавании
                                file_url,
                                f"voice_{file_id}.ogg"
                            )

                            await message.answer(
                                "✅ Голосовое сообщение добавлено в буфер.",
                                reply_markup=get_buffer_keyboard()
                            )
                            return

                        # Сообщаем о начале обработки
                        await message.chat.do(ChatAction.TYPING)

                        # Получаем файл
                        file_id = message.voice.file_id if message.voice else message.audio.file_id
                        file = await message.bot.get_file(file_id)
                        file_path = file.file_path
                        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                        # Отправляем голосовое сообщение в BotHub
                        result = await chat_session_usecase.send_message(user, chat, "", [file_url])

                        if "response" in result and "content" in result["response"]:
                            await message.answer(
                                result["response"]["content"],
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )
                        else:
                            await message.answer(
                                "Не удалось обработать голосовое сообщение.",
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )

                    except Exception as e:
                        logger.error(f"Ошибка при обработке голосового сообщения: {e}", exc_info=True)
                        await message.answer(
                            "❌ Произошла ошибка при обработке голосового сообщения.",
                            parse_mode="Markdown"
                        )

                @router.message(F.photo | F.document)
                async def handle_media_message(message: Message):
                    """Обработка изображений и документов"""
                    try:
                        user = await get_or_create_user(message)
                        chat = await get_or_create_chat(user)

                        # Проверяем режим буфера
                        if user.state == "buffer_mode" and buffer_message_usecase:
                            # Скачиваем файл
                            if message.photo:
                                file_id = message.photo[-1].file_id
                                file_name = f"photo_{file_id}.jpg"
                            else:
                                file_id = message.document.file_id
                                file_name = message.document.file_name or f"document_{file_id}"

                            file = await message.bot.get_file(file_id)
                            file_path = file.file_path
                            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                            # Добавляем в буфер
                            await buffer_message_usecase.add_to_buffer(
                                user,
                                chat,
                                message.caption,
                                file_url,
                                file_name
                            )

                            await message.answer(
                                "✅ Файл добавлен в буфер.",
                                reply_markup=get_buffer_keyboard()
                            )
                            return

                        # Сообщаем о начале обработки
                        await message.chat.do(ChatAction.TYPING)

                        # Получаем файл
                        if message.photo:
                            file_id = message.photo[-1].file_id
                            file_name = f"photo_{file_id}.jpg"
                        else:
                            file_id = message.document.file_id
                            file_name = message.document.file_name or f"document_{file_id}"

                        file = await message.bot.get_file(file_id)
                        file_path = file.file_path
                        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                        # Отправляем файл в BotHub
                        result = await chat_session_usecase.send_message(user, chat, message.caption or "", [file_url])

                        if "response" in result and "content" in result["response"]:
                            await message.answer(
                                result["response"]["content"],
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )
                        else:
                            await message.answer(
                                "Не удалось обработать файл.",
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )

                    except Exception as e:
                        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
                        await message.answer(
                            "❌ Произошла ошибка при обработке файла.",
                            parse_mode="Markdown"
                        )

                @router.message(F.video | F.video_note)
                async def handle_video_message(message: Message):
                    """Обработка видео сообщений"""
                    try:
                        user = await get_or_create_user(message)
                        chat = await get_or_create_chat(user)

                        # Проверяем режим буфера
                        if user.state == "buffer_mode" and buffer_message_usecase:
                            # Скачиваем файл
                            if message.video:
                                file_id = message.video.file_id
                                file_name = f"video_{file_id}.mp4"
                            else:
                                file_id = message.video_note.file_id
                                file_name = f"video_note_{file_id}.mp4"

                            file = await message.bot.get_file(file_id)
                            file_path = file.file_path
                            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                            # Добавляем в буфер
                            await buffer_message_usecase.add_to_buffer(
                                user,
                                chat,
                                message.caption if message.video else None,
                                file_url,
                                file_name
                            )

                            await message.answer(
                                "✅ Видео добавлено в буфер.",
                                reply_markup=get_buffer_keyboard()
                            )
                            return

                        # Сообщаем о начале обработки
                        await message.chat.do(ChatAction.TYPING)

                        # Получаем файл
                        if message.video:
                            file_id = message.video.file_id
                            file_name = f"video_{file_id}.mp4"
                            caption = message.caption or ""
                        else:
                            file_id = message.video_note.file_id
                            file_name = f"video_note_{file_id}.mp4"
                            caption = ""

                        file = await message.bot.get_file(file_id)
                        file_path = file.file_path
                        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

                        # Отправляем видео в BotHub
                        result = await chat_session_usecase.send_message(user, chat, caption, [file_url])

                        if "response" in result and "content" in result["response"]:
                            await message.answer(
                                result["response"]["content"],
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )
                        else:
                            await message.answer(
                                "Не удалось обработать видео.",
                                parse_mode="Markdown",
                                reply_markup=get_main_keyboard(user, chat)
                            )

                    except Exception as e:
                        logger.error(f"Ошибка при обработке видео: {e}", exc_info=True)
                        await message.answer(
                            "❌ Произошла ошибка при обработке видео.",
                            parse_mode="Markdown"
                        )

                    return router
        logger.info("Handlers registered successfully")
        logger.info(f"Returning router of type: {type(router)}")
        return router

    except Exception as e:
        logger.error(f"Error in create_handlers: {e}", exc_info=True)
        raise