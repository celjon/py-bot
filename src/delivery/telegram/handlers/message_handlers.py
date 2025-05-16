from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction
import logging
import time
import os
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Tuple

from src.config.settings import Settings
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, send_long_message, download_telegram_file
from ..services.model_service import show_model_selection
from ..services.keyboard_factory import KeyboardFactory
# Импортируем функцию для обработки команды /gpt_config


logger = logging.getLogger(__name__)

def register_message_handlers(router: Router, chat_session_usecase, intent_detection_service, user_repository,
                              chat_repository, settings):
    """Регистрация обработчиков текстовых сообщений"""

    @router.message(F.text.startswith("🔄 Новый чат"))
    async def handle_new_chat_button(message: Message):
        """Обработка нажатия на кнопку 'Новый чат'"""
        try:
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Сбрасываем счетчик контекста
            chat.reset_context_counter()
            await chat_repository.update(chat)

            # Показываем "печатает"
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

            # Создаем новый чат в BotHub API
            await chat_session_usecase.create_new_chat(user, chat)

            # Формируем сообщение о новом чате с информацией о модели
            model_info = f"Начат новый чат с моделью *{chat.bothub_chat_model or 'по умолчанию'}*"

            # Добавляем информацию о контексте
            if chat.context_remember:
                context_info = "\n\nКонтекст включен. Используйте /reset для сброса контекста."
            else:
                context_info = "\n\nКонтекст отключен. Каждое сообщение обрабатывается отдельно."

            await message.answer(
                f"{model_info}{context_info}",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

            logger.info(f"Создан новый чат для пользователя {user.id} с моделью {chat.bothub_chat_model}")

        except Exception as e:
            logger.error(f"Ошибка при создании нового чата: {str(e)}", exc_info=True)
            await message.answer(
                "Произошла ошибка при создании нового чата. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    # Добавляем обработчик для кнопки "Сменить модель"
    @router.message(F.text.startswith("⚙️ Сменить модель"))
    async def handle_change_model_button(message: Message):
        """Обработка нажатия на кнопку 'Сменить модель'"""
        try:
            await show_model_selection(message, user_repository, chat_repository)
        except Exception as e:
            logger.error(f"Ошибка при смене модели: {str(e)}", exc_info=True)
            await message.answer(
                "Произошла ошибка. Пожалуйста, используйте команду /gpt_config для выбора модели.",
                parse_mode="Markdown"
            )


    @router.message(F.text)
    async def handle_text_message(message: Message):
        """Обработка текстовых сообщений"""
        try:
            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Получаем бота из сообщения
            bot = message.bot

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
            await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

            # Определяем намерение пользователя (чат, поиск, генерация изображений)
            # В этой базовой версии всегда используем чат
            intent_type = "chat"
            intent_data = {"message": message.text}

            logger.info(f"Пользователь {user.id} отправил сообщение: {message.text}")
            logger.info(f"Определено намерение: {intent_type}")

            # Обрабатываем ссылки в тексте, если включен парсинг ссылок
            text = message.text
            if chat.links_parse:
                # В полной версии здесь будет парсинг ссылок
                # text = await links_parser.parse_urls(text)
                pass

            try:
                # Отправляем запрос в BotHub API
                # Проверяем, есть ли у чата ID в BotHub
                if not chat.bothub_chat_id:
                    # Создаем новый чат
                    await chat_session_usecase.create_new_chat(user, chat)

                # Отправляем сообщение и получаем ответ
                result = await chat_session_usecase.send_message(user, chat, text)

                # Если контекст запоминается, увеличиваем счетчик контекста
                if chat.context_remember:
                    chat.increment_context_counter()
                    await chat_repository.update(chat)

                if "response" in result and "content" in result["response"]:
                    content = result["response"]["content"]

                    # Проверяем наличие формул и конвертируем их в изображения, если включено
                    if chat.formula_to_image:
                        # В полной версии здесь будет конвертация формул
                        # content = await formula_service.format_formulas(content)
                        pass

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

                        # Добавляем информацию о контексте, если он включен
                        if chat.context_remember:
                            tokens_info += f"\n\nПродолжить: /continue\n\nСбросить контекст: /reset"

                        await message.answer(
                            tokens_info,
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, chat)
                        )

                    # Если есть вложения (например, изображения), отправляем их
                    if "attachments" in result["response"] and result["response"]["attachments"]:
                        for attachment in result["response"]["attachments"]:
                            if "file" in attachment and attachment["file"].get("type") == "IMAGE":
                                url = attachment["file"].get("url", "")
                                if not url and "path" in attachment["file"]:
                                    url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"

                                if url:
                                    await message.answer_photo(
                                        url,
                                        caption=None,
                                        reply_markup=get_main_keyboard(user, chat)
                                    )

                # Если количество сообщений в контексте достигло кратного 10 значения,
                # напоминаем пользователю о возможности сбросить контекст
                if chat.context_remember and chat.context_counter > 0 and chat.context_counter % 10 == 0:
                    await message.answer(
                        "Совет: Если ваш диалог продолжается уже достаточно долго, для учета всего накопленного "
                        "контекста расходуется больше caps. Чтобы избежать лишних затрат, рекомендуем регулярно "
                        "начинать новый чат с помощью команды /reset.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

            except Exception as api_error:
                logger.error(f"Ошибка при отправке запроса в BotHub API: {api_error}", exc_info=True)
                await message.answer(
                    f"❌ Произошла ошибка при обработке запроса: {str(api_error)}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

        except Exception as e:
            logger.error(f"Общая ошибка при обработке текстового сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз.",
                parse_mode="Markdown"
            )


    @router.message(F.voice)
    async def handle_voice_message(message: Message):
        """Обработка голосовых сообщений"""
        try:
            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)

            # Сообщаем пользователю, что бот обрабатывает голосовое сообщение
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            processing_msg = await message.answer(
                "🎤 Обрабатываю голосовое сообщение...",
                parse_mode="Markdown"
            )

            try:
                # Получаем информацию о файле
                file_id = message.voice.file_id

                # Создаем путь для сохранения
                import tempfile
                import os
                import time
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, f"voice_{int(time.time())}.ogg")

                # Скачиваем файл с помощью нашей вспомогательной функции
                await download_telegram_file(message.bot, settings.TELEGRAM_TOKEN, file_id, temp_file_path)

                # Пока используем заглушку для проверки функциональности
                transcribed_text = "Это тестовое транскрибирование голосового сообщения."

                # В полной реализации:
                # transcribed_text = await chat_session_usecase.transcribe_voice(user, chat, temp_file_path)

                # Удаляем сообщение о загрузке
                await message.bot.delete_message(message.chat.id, processing_msg.message_id)

                # Отправляем результат транскрибирования
                await message.answer(
                    f"🔊 → 📝 Транскрибировано:\n\n{transcribed_text}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

                # Удаляем временный файл
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Временный файл удален: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Ошибка при удалении временного файла: {cleanup_error}")

            except Exception as file_error:
                logger.error(f"Ошибка при обработке файла: {file_error}", exc_info=True)
                await message.bot.delete_message(message.chat.id, processing_msg.message_id)
                await message.answer(
                    "❌ Не удалось скачать голосовое сообщение.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

        except Exception as e:
            logger.error(f"Общая ошибка при обработке голосового сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке голосового сообщения.",
                parse_mode="Markdown"
            )