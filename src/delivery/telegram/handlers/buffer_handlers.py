# Добавление в src/delivery/telegram/handlers/buffer_handlers.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat

logger = logging.getLogger(__name__)


def register_buffer_handlers(router: Router, buffer_usecase, user_repository, chat_repository):
    """Регистрация обработчиков для работы с буфером"""

    @router.message(Command("buffer"))
    async def handle_buffer_command(message: Message):
        """Обработка команды /buffer для входа в режим буфера"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Проверяем, поддерживает ли текущая модель работу с буфером
            if not is_text_model(chat.bothub_chat_model):
                await message.answer(
                    f"❌ Данная функция не поддерживается для выбранной модели {chat.bothub_chat_model}. "
                    f"Пожалуйста, выберите текстовую модель через /gpt\\_config",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            # Включаем режим буфера для пользователя
            user.state = "buffer_mode"
            await user_repository.update(user)

            # Очищаем текущий буфер
            if hasattr(chat, 'buffer') and chat.buffer:
                # В полной версии:
                # await buffer_usecase.clear_buffer(chat)
                chat.buffer = {}
                await chat_repository.update(chat)

            # Создаем клавиатуру для режима буфера
            buffer_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📤 Отправить"), KeyboardButton(text="❌ Отмена")]
                ],
                resize_keyboard=True
            )

            await message.answer(
                "📋 Режим буфера активирован.\n\n"
                "Теперь вы можете отправлять боту несколько сообщений, которые не будут отправлены модели "
                "сразу, а накопятся в буфере.\n\n"
                "Для отправки всех сообщений нажмите кнопку \"📤 Отправить\".\n"
                "Для выхода из режима буфера без отправки нажмите \"❌ Отмена\".",
                parse_mode="Markdown",
                reply_markup=buffer_keyboard
            )

            logger.info(f"Пользователь {user.id} включил режим буфера")

        except Exception as e:
            logger.error(f"Ошибка при включении режима буфера: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при включении режима буфера. Попробуйте позже.",
                parse_mode="Markdown"
            )