from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, send_long_message
from aiogram.enums.chat_action import ChatAction

logger = logging.getLogger(__name__)


def register_chat_handlers(router: Router, chat_session_usecase, user_repository, chat_repository):
    """Регистрация обработчиков команд чата"""

    @router.message(Command("reset"))
    async def handle_reset_command(message: Message):
        """Обработка команды /reset для сброса контекста"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Отправляем информацию о том, что сбрасываем контекст
            await message.answer(
                "🔄 Сбрасываю контекст разговора...",
                parse_mode="Markdown"
            )

            # Сбрасываем контекст через usecase
            await chat_session_usecase.reset_context(user, chat)

            # Обновляем чат в базе данных
            await chat_repository.update(chat)

            await message.answer(
                "✅ Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Пользователь {user.id} сбросил контекст чата {chat.id}")

        except Exception as e:
            logger.error(f"Ошибка сброса контекста: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    @router.message(Command("continue"))
    async def handle_continue_command(message: Message):
        """Обработка команды /continue для продолжения диалога"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Проверяем, включено ли запоминание контекста
            if not chat.context_remember:
                await message.answer(
                    "⚠️ Запоминание контекста отключено. Включите его с помощью команды /context",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            # Отправляем запрос на продолжение разговора
            # Сообщаем пользователю, что бот печатает
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

            # Отправляем запрос в BotHub API
            result = await chat_session_usecase.send_message(user, chat, "Продолжай")

            # Увеличиваем счетчик контекста
            chat.increment_context_counter()
            await chat_repository.update(chat)

            if "response" in result and "content" in result["response"]:
                content = result["response"]["content"]

                # Если сообщение слишком длинное, разбиваем его
                if len(content) > 4000:
                    await send_long_message(message, content)
                else:
                    await message.answer(
                        content,
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                # Если есть информация о токенах, отправляем её
                if "tokens" in result:
                    tokens_info = f"`-{result['tokens']} caps`"

                    # Добавляем информацию о контексте
                    tokens_info += f"\n\nПродолжить: /continue\n\nСбросить контекст: /reset"

                    await message.answer(
                        tokens_info,
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

            logger.info(f"Пользователь {user.id} продолжил диалог в чате {chat.id}")

        except Exception as e:
            logger.error(f"Ошибка при продолжении диалога: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось продолжить диалог. Попробуйте еще раз.",
                parse_mode="Markdown"
            )