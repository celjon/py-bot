# src/delivery/telegram/handlers/message_handlers.py
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
from src.domain.service.intent_detection import IntentType

logger = logging.getLogger(__name__)


def register_message_handlers(router: Router, chat_session_usecase, image_generation_usecase, intent_detection_service,
                              user_repository,
                              chat_repository, settings):
    """Регистрация обработчиков текстовых сообщений"""

    async def process_image_generation(message: Message, user, chat, prompt):
        """Обработка запроса на генерацию изображения"""
        logger.info(f"🎨 Начало обработки запроса на генерацию изображения от пользователя {user.id}")
        logger.info(f"🎨 Промпт для генерации: '{prompt}'")

        bot = message.bot

        # Отправляем сообщение о генерации
        logger.info(f"🎨 Отправка сообщения о начале генерации изображения")
        processing_msg = await message.answer(
            "🎨 Генерирую изображение...",
            parse_mode="Markdown"
        )

        try:
            # Отправляем статус "uploading_photo"
            logger.info(f"🎨 Отправка статуса 'uploading_photo'")
            await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

            # Генерируем изображение без видимого переключения чата
            logger.info(f"🎨 Вызов usecase для генерации изображения")
            result, model_used = await image_generation_usecase.generate_image_without_switching_chat(user, chat,
                                                                                                      prompt)
            logger.info(f"🎨 Получен результат генерации, модель: {model_used}")
            logger.info(f"🎨 Результат: {result}")

            # Удаляем сообщение о генерации
            try:
                logger.info(f"🎨 Удаление сообщения о генерации")
                await bot.delete_message(message.chat.id, processing_msg.message_id)
            except Exception as e:
                logger.error(f"🎨 Ошибка при удалении сообщения о генерации: {e}")

            # Обрабатываем результат
            if "response" in result and "attachments" in result["response"] and result["response"]["attachments"]:
                # Находим изображения в ответе
                logger.info(f"🎨 Обработка вложений из ответа")
                images = []
                for attachment in result["response"]["attachments"]:
                    if "file" in attachment and attachment["file"].get("type") == "IMAGE":
                        url = attachment["file"].get("url", "")
                        if not url and "path" in attachment["file"]:
                            url = f"https://storage.bothub.chat/bothub-storage/{attachment['file']['path']}"
                        if url:
                            logger.info(f"🎨 Найдено изображение: {url}")
                            images.append(url)

                # Отправляем изображения пользователю
                if images:
                    logger.info(f"🎨 Отправка {len(images)} изображений пользователю")
                    for url in images:
                        logger.info(f"🎨 Отправка изображения: {url}")
                        await message.answer_photo(
                            url,
                            caption=f"🎨 Изображение сгенерировано с использованием модели *{model_used}*",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard(user, chat)
                        )

                    # Если есть информация о токенах, отправляем её
                    if "tokens" in result:
                        logger.info(f"🎨 Отправка информации о токенах: {result['tokens']}")
                        await message.answer(
                            f"`-{result['tokens']} caps`",
                            parse_mode="Markdown"
                        )

                    # Обновляем контекст пользователя в сервисе определения намерений
                    logger.info(f"🎨 Обновление контекста пользователя")
                    intent_detection_service.update_user_context(str(user.telegram_id),
                                                                 IntentType.IMAGE_GENERATION,
                                                                 {"prompt": prompt, "success": True})
                    return

                logger.info(f"🎨 Изображения не найдены в ответе")
            else:
                logger.info(f"🎨 Вложения не найдены в ответе")

            # Если не удалось сгенерировать изображение
            logger.info(f"🎨 Не удалось сгенерировать изображение, отправка сообщения об ошибке")
            await message.answer(
                "❌ Не удалось сгенерировать изображение. Пожалуйста, попробуйте другой запрос.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(user, chat)
            )

        except Exception as e:
            logger.error(f"🎨 Ошибка при генерации изображения: {e}", exc_info=True)

            error_message = str(e)
            # Проверяем, содержит ли ошибка код "MODEL_NOT_FOUND"
            if "MODEL_NOT_FOUND" in error_message:
                logger.info(f"🎨 Обнаружена ошибка MODEL_NOT_FOUND")
                await message.answer(
                    "❌ Не удалось сгенерировать изображение. В вашем аккаунте нет доступа к моделям генерации изображений. "
                    "Пожалуйста, проверьте подписку или свяжитесь с поддержкой.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
            elif "NOT_ENOUGH_TOKENS" in error_message:
                logger.info(f"🎨 Обнаружена ошибка NOT_ENOUGH_TOKENS")
                await message.answer(
                    "❌ Не удалось сгенерировать изображение. На вашем аккаунте недостаточно токенов. "
                    "Пожалуйста, пополните баланс или привяжите аккаунт с достаточным количеством токенов.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )
            else:
                logger.info(f"🎨 Обнаружена общая ошибка: {error_message}")
                await message.answer(
                    "❌ Произошла ошибка при генерации изображения. Пожалуйста, попробуйте позже.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

    @router.message(F.text == "🎨 Сменить модель изображений")
    async def handle_image_model_button(message: Message):
        """Обработка нажатия на кнопку смены модели генерации изображений"""
        try:
            # Делегируем обработку команде /image_model
            # Эта функция будет определена в image_handlers.py
            from .image_handlers import handle_image_model_command
            await handle_image_model_command(message)
        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки смены модели изображений: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
                parse_mode="Markdown"
            )

    @router.message(F.text)
    async def handle_text_message(message: Message):
        """Обработка текстовых сообщений"""
        try:
            logger.info(f"Получено сообщение: {message.text} от пользователя {message.from_user.id}")
            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message, user_repository)
            logger.info(f"Получен пользователь: {user.id}, {user.first_name}")
            chat = await get_or_create_chat(user, chat_repository)
            logger.info(f"Получен чат: {chat.id}, bothub_chat_id: {chat.bothub_chat_id}")

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
            elif message.text == "🔄 Новый чат":
                try:
                    # Создаем новый чат
                    await message.answer(
                        "🔄 Создаю новый чат...",
                        parse_mode="Markdown"
                    )

                    # Сбрасываем контекст текущего чата
                    chat.reset_context_counter()
                    await chat_repository.update(chat)

                    # Создаем новый чат через usecase
                    await chat_session_usecase.create_new_chat(user, chat)

                    model_name = chat.bothub_chat_model or "default"
                    await message.answer(
                        f"✅ Новый чат создан с моделью *{model_name}*.\n\nТеперь вы можете продолжить общение.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                    logger.info(f"Пользователь {user.id} создал новый чат")
                except Exception as e:
                    logger.error(f"Ошибка при создании нового чата: {e}", exc_info=True)
                    await message.answer(
                        "❌ Не удалось создать новый чат. Пожалуйста, попробуйте позже.",
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

            # Определяем намерение пользователя (чат, поиск, генерация изображений)
            intent_type, intent_data = intent_detection_service.detect_intent(message.text, str(message.from_user.id))

            logger.info(f"Пользователь {user.id} отправил сообщение: {message.text}")
            logger.info(f"Определено намерение: {intent_type}")

            # Если это запрос на генерацию изображения
            if intent_type == IntentType.IMAGE_GENERATION:
                # Обновляем контекст пользователя
                intent_detection_service.update_user_context(str(message.from_user.id), intent_type, intent_data)

                # Получаем промпт для генерации изображения
                image_prompt = intent_data.get("prompt", message.text)

                # Обрабатываем запрос на генерацию изображения
                await process_image_generation(message, user, chat, image_prompt)
                return

            # Сообщаем пользователю, что бот печатает
            await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

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
            logger.info("[VOICE] Начало обработки голосового сообщения")

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)
            logger.info(f"[VOICE] Пользователь: {user.id}, чат: {chat.id}")

            # Получаем настройки
            from src.config.settings import get_settings
            settings = get_settings()

            # Сообщаем пользователю, что бот обрабатывает голосовое сообщение
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
            processing_msg = await message.answer(
                "🎤 Обрабатываю голосовое сообщение...",
                parse_mode="Markdown"
            )

            try:
                # Получаем информацию о голосовом сообщении
                file_id = message.voice.file_id
                duration = message.voice.duration
                file_size = message.voice.file_size if hasattr(message.voice, 'file_size') else 'unknown'
                mime_type = message.voice.mime_type if hasattr(message.voice, 'mime_type') else 'audio/ogg'

                logger.info(
                    f"[VOICE] Получено голосовое сообщение: file_id={file_id}, duration={duration}s, size={file_size}, mime_type={mime_type}")

                # Скачиваем файл с голосовым сообщением
                temp_file_path = await download_telegram_file(message.bot, file_id, None, settings)
                logger.info(f"[VOICE] Голосовое сообщение сохранено в {temp_file_path}")

                # Проверяем, что файл существует и имеет нормальный размер
                if not os.path.exists(temp_file_path):
                    logger.error(f"[VOICE] Файл не существует: {temp_file_path}")
                    raise Exception("Файл не был сохранен")

                actual_file_size = os.path.getsize(temp_file_path)
                logger.info(f"[VOICE] Размер сохраненного файла: {actual_file_size} байт")

                if actual_file_size < 100:
                    logger.warning(f"[VOICE] Файл слишком маленький ({actual_file_size} байт)")
                    await message.bot.delete_message(message.chat.id, processing_msg.message_id)
                    await message.answer(
                        "⚠️ Извините, аудиофайл слишком маленький. Пожалуйста, отправьте более длинное голосовое сообщение.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                    return

                # Отправляем на транскрибацию
                logger.info(f"[VOICE] Отправляем файл {temp_file_path} на транскрибацию")
                transcribed_text = await chat_session_usecase.transcribe_voice(user, chat, temp_file_path)
                logger.info(f"[VOICE] Результат транскрибации: {transcribed_text[:100]}...")

                # После транскрибации удаляем временный файл
                try:
                    os.remove(temp_file_path)
                    logger.info(f"[VOICE] Временный файл удален: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.error(f"[VOICE] Ошибка при удалении временного файла: {cleanup_error}")

                # Удаляем сообщение о загрузке
                try:
                    await message.bot.delete_message(message.chat.id, processing_msg.message_id)
                except Exception as delete_error:
                    logger.error(f"[VOICE] Ошибка при удалении сообщения: {delete_error}")

                # Отправляем результат транскрибации
                await message.answer(
                    f"🔊 → 📝 Распознанный текст:\n\n{transcribed_text}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

                # Отправляем распознанный текст в чат с ИИ
                await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

                result = await chat_session_usecase.send_message(user, chat, transcribed_text)

                if "response" in result and "content" in result["response"]:
                    content = result["response"]["content"]
                    await send_long_message(message, content)

                    # Если есть токены, отправляем информацию о них
                    if "tokens" in result:
                        await message.answer(
                            f"👾 -{result['tokens']} caps",
                            parse_mode="Markdown"
                        )

            except Exception as file_error:
                logger.error(f"[VOICE] Ошибка при обработке файла: {file_error}", exc_info=True)
                # Удаляем сообщение о загрузке
                try:
                    await message.bot.delete_message(message.chat.id, processing_msg.message_id)
                except Exception:
                    pass

                await message.answer(
                    "❌ Не удалось обработать голосовое сообщение. Пожалуйста, попробуйте отправить текстовое сообщение.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard(user, chat)
                )

        except Exception as e:
            logger.error(f"[VOICE] Общая ошибка при обработке голосового сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке голосового сообщения. Пожалуйста, попробуйте позже.",
                parse_mode="Markdown"
            )