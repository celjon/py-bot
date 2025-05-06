from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction
import logging
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, send_long_message

logger = logging.getLogger(__name__)


def register_message_handlers(router: Router, chat_session_usecase, intent_detection_service, user_repository,
                              chat_repository):
    """Регистрация обработчиков текстовых сообщений"""

    @router.message(F.text)
    async def handle_text_message(message: Message):
        """Обработка текстовых сообщений с умным определением намерения"""
        try:
            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Проверяем, находится ли пользователь в каком-то состоянии
            if user.state == "waiting_for_chat_name":
                # Это часть логики создания нового чата
                # Просто отвечаем для демонстрации
                await message.answer(
                    "Режим создания чата активен. Этот функционал будет реализован позже.",
                    parse_mode="Markdown"
                )
                user.state = None
                await user_repository.update(user)
                return

            # Проверяем, находится ли пользователь в режиме буфера
            elif user.state == "buffer_mode":
                # Это часть логики работы с буфером
                # Просто отвечаем для демонстрации
                await message.answer(
                    "Режим буфера активен. Этот функционал будет реализован позже.",
                    parse_mode="Markdown"
                )
                user.state = None
                await user_repository.update(user)
                return

            # Проверяем, не является ли сообщение командой клавиатуры
            if message.text == "🔄 Новый чат":
                await message.answer(
                    "Функция создания нового чата будет реализована позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            elif message.text == "🎨 Генерация изображений":
                await message.answer(
                    "Функция генерации изображений будет реализована позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            elif message.text.startswith("🔍 Поиск в интернете"):
                await message.answer(
                    "Функция веб-поиска будет реализована позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            elif message.text == "⚙️ Инструменты":
                await message.answer(
                    "⚙️ Инструменты:\n\n"
                    "/gpt_config - Настройка моделей для текста\n"
                    "/link_account - Привязать аккаунт\n"
                    "/reset - Сбросить контекст\n"
                    "/help - Получить справку",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            elif message.text == "📋 Буфер":
                await message.answer(
                    "Функция работы с буфером будет реализована позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
                return

            # Проверяем, не является ли сообщение кнопкой чата
            chat_emojis = {"1️⃣": 1, "2️⃣": 2, "3️⃣": 3, "4️⃣": 4, "📝": 5}
            for emoji, index in chat_emojis.items():
                if message.text.startswith(emoji):
                    user.current_chat_index = index
                    await user_repository.update(user)

                    chat = await get_or_create_chat(user, chat_repository)

                    await message.answer(
                        f"✅ Выбран чат {index}" + (f" | {chat.name}" if chat.name else ""),
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )
                    return

            # Сообщаем пользователю, что бот печатает
            await message.chat.do(ChatAction.TYPING)

            # Определяем намерение пользователя
            # В данной демо-версии просто эхо
            logger.info(f"Пользователь {user.id} отправил сообщение: {message.text}")

            # В финальной версии здесь будет использован intent_detection_service
            # и chat_session_usecase, но пока просто отвечаем эхом

            try:
                # Имитация ответа от BotHub
                result = {"response": {
                    "content": f"Вы написали: {message.text}\n\nЭто демо-версия бота, полный функционал будет реализован позже."}}

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

    # Отладочный обработчик, который будет отвечать на любое входящее сообщение
    # Можно использовать для проверки, что маршрутизация работает
    @router.message()
    async def handle_any_message(message: Message):
        try:
            logger.info(f"Получено сообщение любого типа от {message.from_user.id}")

            if hasattr(message, 'text') and message.text:
                await message.answer(f"Получил ваше сообщение: {message.text}")
            else:
                await message.answer("Получил ваше сообщение, но это не текст")

        except Exception as e:
            logger.error(f"Ошибка при обработке любого сообщения: {e}", exc_info=True)