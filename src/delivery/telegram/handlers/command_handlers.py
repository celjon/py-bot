from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, get_user_from_telegram_user

logger = logging.getLogger(__name__)


def register_command_handlers(router: Router, chat_session_usecase, user_repository, chat_repository):
    """Регистрация обработчиков базовых команд"""

    @router.message(Command("start"))
    async def handle_start_command(message: Message):
        """Обработка команды /start"""
        try:
            # Получаем или создаём пользователя и чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Проверяем наличие реферального кода
            if message.text and len(message.text.split()) > 1:
                user.referral_code = message.text.split()[1]
                await user_repository.update(user)

            # Отправляем приветственное сообщение
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
                "/gpt\\_config - настройка моделей для текста\n"
                "/link\\_account - привязать аккаунт к существующему аккаунту BotHub",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} использовал команду /start")

        except Exception as e:
            logger.error(f"Ошибка при обработке команды /start: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке команды",
                parse_mode="Markdown"
            )

    @router.message(Command("help"))
    async def handle_help_command(message: Message):
        """Обработка команды /help для вывода справки"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            await message.answer(
                "📚 *Справка по командам бота*\n\n"
                "/start - Начать общение с ботом\n"
                "/reset - Сбросить контекст разговора\n"
                "/link\\_account - Привязать аккаунт Telegram к существующему аккаунту BotHub\n"
                "/gpt\\_config - Настройка моделей для текстовой генерации\n\n"
                "Вы также можете просто написать мне, что вы хотите, и я автоматически определю "
                "ваше намерение (чат, поиск или генерация изображений).",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} использовал команду /help")

        except Exception as e:
            logger.error(f"Ошибка при обработке команды /help: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось обработать команду. Попробуйте позже.",
                parse_mode="Markdown"
            )

