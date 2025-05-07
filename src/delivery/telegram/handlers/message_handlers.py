# src/delivery/telegram/handlers/message_handlers.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction
import logging
import os
import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple

from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, send_long_message, download_file_custom

logger = logging.getLogger(__name__)


def register_message_handlers(router: Router, chat_session_usecase, intent_detection_service, user_repository,
                              chat_repository):
    """Регистрация обработчиков текстовых сообщений"""

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

            # Создаём временную директорию, если её нет
            import tempfile
            import os
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"voice_{message.voice.file_id}.ogg")

            try:
                # Получаем информацию о файле
                file_info = await message.bot.get_file(message.voice.file_id)

                # Логируем информацию о файле для отладки
                logger.info(f"Файл получен: {file_info}")
                logger.info(f"Путь к файлу: {file_info.file_path}")

                # Для локального Telegram Bot API сервера нужно обращаться напрямую
                # к директории с файлами, а не скачивать через HTTP
                from src.config.settings import get_settings
                settings = get_settings()

                # Проверяем, содержит ли путь к файлу полный путь или только имя
                if os.path.isabs(file_info.file_path):
                    # Если это полный путь, используем его напрямую
                    telegram_file_path = file_info.file_path
                else:
                    # Иначе формируем путь из базовой директории API сервера
                    # Если файл находится на локальном сервере, он должен быть доступен
                    # в директории, настроенной в settings.TELEGRAM_API_DATA_DIR
                    # Или можно использовать стандартный путь из конфигурации Docker
                    telegram_file_path = "/telegram-bot-api-data/" + file_info.file_path

                # Скопируем файл на временный путь
                import shutil

                # Проверяем существование исходного файла
                if os.path.exists(telegram_file_path):
                    shutil.copy(telegram_file_path, temp_file_path)
                    logger.info(f"Файл скопирован: {telegram_file_path} -> {temp_file_path}")
                else:
                    # Если файл не найден на диске, попробуем загрузить через HTTP
                    import aiohttp

                    # Используем базовый URL API из конфигурации
                    api_url = settings.TELEGRAM_API_URL
                    file_url = f"{api_url}/file/bot{message.bot.token}/{file_info.file_path}"

                    logger.info(f"Пробуем скачать файл через HTTP: {file_url}")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as response:
                            if response.status != 200:
                                raise Exception(f"Не удалось скачать файл: HTTP {response.status}")

                            # Сохраняем содержимое файла
                            with open(temp_file_path, "wb") as f:
                                f.write(await response.read())

                    logger.info(f"Файл успешно скачан через HTTP и сохранен: {temp_file_path}")

                # Логируем успешное получение файла
                logger.info(f"Файл успешно получен и сохранен: {temp_file_path}")

                # Здесь должен быть вызов транскрибирования, но пока используем заглушку
                transcribed_text = "Тестовое транскрибирование голосового сообщения. Реальная функциональность будет реализована позже."

                # Удаляем сообщение о загрузке
                await message.bot.delete_message(message.chat.id, processing_msg.message_id)

                # Отправляем текст транскрибирования
                await message.answer(
                    f"🔊 → 📝 Транскрибировано:\n\n{transcribed_text}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

            except Exception as file_error:
                logger.error(f"Ошибка при работе с файлом: {file_error}", exc_info=True)
                await message.bot.delete_message(message.chat.id, processing_msg.message_id)
                await message.answer(
                    f"❌ Ошибка при обработке файла: {str(file_error)}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

            # Удаляем временный файл, если он существует
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.info(f"Временный файл удален: {temp_file_path}")
            except Exception as cleanup_error:
                logger.error(f"Ошибка при удалении временного файла: {cleanup_error}")

        except Exception as e:
            logger.error(f"Общая ошибка при обработке голосового сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке голосового сообщения.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )