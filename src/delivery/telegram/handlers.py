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
from src.domain.usecase.system_prompt import SystemPromptUseCase
from src.domain.usecase.present import PresentUseCase
from src.domain.usecase.referral import ReferralUseCase
from src.domain.usecase.model_selection import ModelSelectionUseCase
from src.domain.service.chat_service import ChatService
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
from src.adapter.repository.present_repository import PresentRepository
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
        system_prompt_usecase: SystemPromptUseCase,
        present_usecase: PresentUseCase,
        referral_usecase: ReferralUseCase,
        model_selection_usecase: ModelSelectionUseCase,
        chat_service: ChatService,
        intent_detection_service: IntentDetectionService,
        user_repository: UserRepository,
        chat_repository: ChatRepository,
        present_repository: PresentRepository
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

    # ==================== ГЕНЕРАТОРЫ КЛАВИАТУР ====================

    def get_main_keyboard(user: User, chat: Chat) -> List[List[str]]:
        """Создание основной клавиатуры бота"""
        # Получаем кнопки чатов
        chat_buttons = chat_service.get_chat_buttons(user.current_chat_index)

        # Проверяем, включен ли веб-поиск
        web_search_text = "🔍 Поиск в интернете"
        if hasattr(chat, 'web_search_enabled') and chat.web_search_enabled:
            web_search_text += " ✅"
        else:
            web_search_text += " ❌"

        # Формируем клавиатуру
        keyboard = [
            ["🔄 Новый чат", web_search_text, "🎨 Генерация изображений"],
            ["⚙️ Инструменты", "📋 Буфер"] + chat_buttons
        ]

        return keyboard

    def get_chat_model_inline_keyboard(models: List[Dict], current_model: Optional[str] = None) -> InlineKeyboardMarkup:
        """Возвращает инлайн-клавиатуру для выбора модели чата"""
        buttons = []

        # Фильтруем только модели для текстовой генерации
        text_models = model_selection_usecase.filter_text_models(models)

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
        image_models = model_selection_usecase.filter_image_models(models)

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

    def get_referral_templates_inline_keyboard(templates: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
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

    @dp.message(Command("start"))
    async def handle_start_command(message: Message):
        """Обработка команды /start"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

            # Проверяем наличие реферального кода
            if message.text and len(message.text.split()) > 1:
                user.referral_code = message.text.split()[1]
                await user_repository.update(user)

            # Отправляем уведомления о подарках, если есть
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
                reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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
            chat = await chat_service.get_or_create_chat(user)

            # Сбрасываем контекст
            await chat_service.reset_context(user, chat)

            await message.answer(
                "🔄 Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                parse_mode="Markdown",
                reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("image_generation_config"))
    async def handle_image_generation_config_command(message: Message):
        """Обработка команды /image_generation_config для настройки моделей генерации изображений"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("context"))
    async def handle_context_command(message: Message):
        """Обработка команды /context для управления контекстом"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

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
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("system_prompt"))
    async def handle_system_prompt_command(message: Message):
        """Обработка команды /system_prompt для управления системным промптом"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

            # Проверяем, есть ли у сообщения текст после команды
            command_text = message.text.strip()
            parts = command_text.split(maxsplit=1)

            if len(parts) > 1:
                # Если есть текст после команды, устанавливаем его как системный промпт
                new_prompt = parts[1]
                await system_prompt_usecase.set_system_prompt(user, chat, new_prompt)
                await message.answer(
                    f"✅ Системный промпт установлен:\n\n{new_prompt}",
                    parse_mode="Markdown",
                    reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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

    @dp.message(Command("formula"))
    async def handle_formula_command(message: Message):
        """Обработка команды /formula для управления конвертацией формул в изображения"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("scan_links"))
    async def handle_scan_links_command(message: Message):
        """Обработка команды /scan_links для управления парсингом ссылок"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("voice"))
    async def handle_voice_command(message: Message):
        """Обработка команды /voice для управления ответами голосом"""
        try:
            user = await get_or_create_user(message)
            chat = await chat_service.get_or_create_chat(user)

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

    @dp.message(Command("present"))
    async def handle_present_command(message: Message):
        """Обработка команды /present для подарка токенов"""
        try:
            user = await get_or_create_user(message)

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
                        reply_markup={"keyboard": get_main_keyboard(user, await chat_service.get_or_create_chat(user)),
                                      "resize_keyboard": True}
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

    @dp.message(Command("referral"))
    async def handle_referral_command(message: Message):
        """Обработка команды /referral для управления реферальной программой"""
        try:
            user = await get_or_create_user(message)

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

        @dp.message(Command("chat_list"))
        async def handle_chat_list_command(message: Message):
            """Обработка команды /chat_list для просмотра списка чатов"""
            try:
                user = await get_or_create_user(message)

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

        @dp.callback_query()
        async def handle_callback_query(callback: CallbackQuery):
            """Обработка всех callback-запросов от инлайн клавиатуры"""
            try:
                user = await get_or_create_user(callback.message)
                chat = await chat_service.get_or_create_chat(user)

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
                    await model_selection_usecase.select_chat_model(user, chat, model_id)
                    await user_repository.update(user)
                    await chat_repository.update(chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer(f"Модель {model_id} выбрана")
                    await callback.message.answer(
                        f"✅ Модель *{model_id}* успешно выбрана и новый чат создан.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "select_image_model":
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
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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
                    await chat_service.update_chat_settings(chat, context_remember=True)

                    # Создаем новый чат с активным контекстом
                    await chat_session_usecase.gateway.create_new_chat(user, chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Контекст включен")
                    await callback.message.answer(
                        "✅ Контекст включен. Теперь я буду помнить предыдущие сообщения.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "context_off":
                    # Выключаем контекст
                    await chat_service.update_chat_settings(chat, context_remember=False)

                    # Создаем новый чат с выключенным контекстом
                    await chat_session_usecase.gateway.create_new_chat(user, chat)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Контекст выключен")
                    await callback.message.answer(
                        "✅ Контекст выключен. Теперь я не буду помнить предыдущие сообщения.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "formula_to_image_on":
                    # Включаем конвертацию формул в изображения
                    await chat_service.update_chat_settings(chat, formula_to_image=True)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Конвертация формул включена")
                    await callback.message.answer(
                        "✅ Конвертация формул в изображения включена.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "formula_to_image_off":
                    # Выключаем конвертацию формул в изображения
                    await chat_service.update_chat_settings(chat, formula_to_image=False)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Конвертация формул выключена")
                    await callback.message.answer(
                        "✅ Конвертация формул в изображения выключена.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "links_parse_on":
                    # Включаем парсинг ссылок
                    await chat_service.update_chat_settings(chat, links_parse=True)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Парсинг ссылок включен")
                    await callback.message.answer(
                        "✅ Парсинг ссылок включен.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "links_parse_off":
                    # Выключаем парсинг ссылок
                    await chat_service.update_chat_settings(chat, links_parse=False)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Парсинг ссылок выключен")
                    await callback.message.answer(
                        "✅ Парсинг ссылок выключен.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "voice_answer_on":
                    # Включаем ответы голосом
                    await chat_service.update_chat_settings(chat, answer_to_voice=True)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Ответы голосом включены")
                    await callback.message.answer(
                        "✅ Ответы голосом включены.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "voice_answer_off":
                    # Выключаем ответы голосом
                    await chat_service.update_chat_settings(chat, answer_to_voice=False)

                    # Обновляем сообщение и отвечаем пользователю
                    await callback.message.delete_reply_markup()
                    await callback.answer("Ответы голосом выключены")
                    await callback.message.answer(
                        "✅ Ответы голосом выключены.",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                    )

                elif action == "chat_page":
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
                            reply_markup={"keyboard": get_main_keyboard(user, selected_chat), "resize_keyboard": True}
                        )
                    else:
                        await callback.answer("Чат не найден")

                elif action == "create_new_chat":
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
                            reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при создании реферальной программы: {e}", exc_info=True)
                        await callback.message.delete_reply_markup()
                        await callback.message.answer(
                            f"❌ Не удалось создать реферальную программу: {str(e)}",
                            parse_mode="Markdown",
                            reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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
                            reply_markup={
                                "keyboard": get_main_keyboard(user, await chat_service.get_or_create_chat(user)),
                                "resize_keyboard": True}
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
                    new_chat = await chat_service.create_new_chat(user, chat_name)
                    user.state = None
                    await user_repository.update(user)

                    await message.answer(
                        f"✅ Создан новый чат: {chat_name}",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, new_chat), "resize_keyboard": True}
                    )
                    return

                # Проверяем, не является ли сообщение командой клавиатуры
                if message.text == "🔄 Новый чат":
                    # Создаем новый чат с текущей моделью
                    chat = await chat_service.get_or_create_chat(user)
                    await chat_session_usecase.gateway.create_new_chat(user, chat)
                    chat.reset_context_counter()
                    await chat_repository.update(chat)

                    await message.answer(
                        f"✅ Создан новый чат с моделью {chat.bothub_chat_model or 'по умолчанию'}",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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
                    # Переключаем статус веб-поиска
                    chat = await chat_service.get_or_create_chat(user)
                    current_status = await web_search_usecase.gateway.get_web_search(user, chat)
                    new_status = not current_status

                    await web_search_usecase.toggle_web_search(user, chat, new_status)

                    status_text = "включен" if new_status else "выключен"
                    await message.answer(
                        f"🔍 Веб-поиск {status_text}",
                        parse_mode="Markdown",
                        reply_markup={"keyboard": get_main_keyboard(user, chat), "resize_keyboard": True}
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

                    await message.answer(
                        "📋 Режим буфера активирован.\n\n"
                        "Отправьте сообщения и файлы, которые нужно добавить в буфер.\n"
                        "Когда закончите, отправьте команду `/send_buffer`, чтобы отправить все сообщения из буфера.\n"
                        "Для отмены отправьте `/cancel`.",
                        parse_mode="Markdown"
                    )
                    return

                # Проверяем, не является ли сообщение кнопкой чата
                chat_index = chat_service.parse_chat_button(message.text)
                if chat_index is not None:
                    # Переключаемся на выбранный чат
                    selected_chat = await chat_service.switch_chat(user, chat_index)

                    if selected_chat:
                        await user_repository.update(user)

                        await message.answer(
                            f"✅ Выбран чат {chat_index}" + (f" | {selected_chat.name}" if selected_chat.name else ""),
                            parse_mode="Markdown",
                            reply_markup={"keyboard": get_main_keyboard(user, selected_chat), "resize_keyboard": True}
                        )
                    else:
                        await message.answer(
                            "❌ Чат не найден.",
                            parse_mode="Markdown"
                        )
                    return

                # Сообщаем пользователю, что бот печатает
                await message.chat.do(ChatAction.TYPING)

                # Получаем текущий чат пользователя
                chat = await chat_service.get_or_create_chat(user)

                # Определяем намерение пользователя
                intent, intent_data = intent_detection_service.detect_intent(
                    message.text,
                    str(user.id),  # Используем ID пользователя для контекста
                    None  # Пока не используем историю чата
                )

                # Обновляем контекст намерений пользователя
                intent_detection_service.update_user_context(str(user.i  # src/delivery/telegram/handlers.py