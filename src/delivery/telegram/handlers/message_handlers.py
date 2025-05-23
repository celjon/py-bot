# src/delivery/telegram/handlers/message_handlers.py
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.enums.chat_action import ChatAction
import logging
import time
import os
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import uuid
from urllib.parse import urlparse
import json

from src.config.settings import Settings
from ..keyboards.main_keyboard import get_main_keyboard
from .base_handlers import get_or_create_user, get_or_create_chat, send_long_message, download_telegram_file
from src.domain.service.intent_detection import IntentType

logger = logging.getLogger(__name__)


def register_message_handlers(router: Router, chat_session_usecase, image_generation_usecase, intent_detection_service,
                              user_repository,
                              chat_repository, settings):
    """Регистрация обработчиков текстовых сообщений"""

    async def download_image(url: str) -> Optional[str]:
        """Скачивает изображение и возвращает путь к временному файлу"""
        logger.info(f"⬇️ Загрузка изображения с URL: {url}")
        
        # Проверка пустой ссылки
        if not url:
            logger.error("⬇️ Передан пустой URL")
            return None
            
        # Проверка для локальных путей в URL
        if "local/images" in url:
            logger.warning(f"⬇️ URL содержит указание на локальное хранилище: {url}")
            # Изображение может быть недоступно извне, но попробуем скачать
        
        # Проверим валидность URL
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.error(f"⬇️ Некорректный URL: {url}")
                return None
        except Exception as e:
            logger.error(f"⬇️ Ошибка при парсинге URL {url}: {e}")
            return None
            
        try:
            # Создаем временную директорию, если она не существует
            temp_dir = os.path.join(tempfile.gettempdir(), "telegram_bot_images")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Генерируем уникальное имя файла
            file_extension = os.path.splitext(url)[-1]
            if not file_extension or len(file_extension) < 2:
                file_extension = ".jpg"  # Устанавливаем расширение по умолчанию
                
            filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(temp_dir, filename)
            
            # Скачиваем файл с таймаутом
            async with aiohttp.ClientSession() as session:
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        async with session.get(url, timeout=30, allow_redirects=True) as response:
                            if response.status == 404:
                                logger.error(f"⬇️ Файл не найден на сервере (404): {url}")
                                return None
                                
                            if response.status != 200:
                                logger.error(f"⬇️ Ошибка при загрузке изображения: HTTP {response.status}")
                                if retry < max_retries - 1:
                                    wait_time = 2 ** retry  # Экспоненциальная задержка
                                    logger.info(f"⬇️ Повторная попытка через {wait_time} сек...")
                                    await asyncio.sleep(wait_time)
                                continue
                                
                            # Проверяем mime-type для убеждения что это изображение
                            content_type = response.headers.get('Content-Type', '')
                            if not content_type.startswith('image/'):
                                logger.warning(f"⬇️ Скачанный файл не является изображением: {content_type}")
                                # Все равно попытаемся использовать файл
                            
                            # Получаем данные файла
                            file_data = await response.read()
                            if not file_data or len(file_data) < 100:
                                logger.error(f"⬇️ Слишком маленький размер файла: {len(file_data) if file_data else 0} байт")
                                if retry < max_retries - 1:
                                    continue
                                return None
                            
                            # Записываем файл
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            
                            # Проверим, что файл действительно создан и имеет размер
                            if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
                                logger.info(f"⬇️ Изображение успешно загружено: {file_path}")
                                return file_path
                            else:
                                logger.error(f"⬇️ Файл не создан или имеет недопустимый размер: {os.path.getsize(file_path) if os.path.exists(file_path) else 'не существует'}")
                                if retry < max_retries - 1:
                                    continue
                                return None
                    except aiohttp.ClientConnectorError as e:
                        logger.error(f"⬇️ Ошибка подключения к серверу: {e}")
                        # Если сервер недоступен, нет смысла повторять запрос сразу
                        return None
                    except asyncio.TimeoutError:
                        logger.error(f"⬇️ Таймаут при загрузке изображения (попытка {retry+1}/{max_retries})")
                        if retry < max_retries - 1:
                            await asyncio.sleep(2 ** retry)
                    except Exception as e:
                        logger.error(f"⬇️ Неожиданная ошибка при загрузке изображения: {e}")
                        if retry < max_retries - 1:
                            await asyncio.sleep(1)
                        else:
                            break
                
                logger.error(f"⬇️ Не удалось загрузить изображение после {max_retries} попыток")
                return None
        except Exception as e:
            logger.error(f"⬇️ Ошибка при скачивании изображения: {e}")
            return None

    async def process_image_generation(message: Message) -> None:
        """Обработчик генерации изображений"""
        start_time = time.time()
        logger.info(f"🖼️ Запрос на генерацию изображения с текстом: {message.text}")

        # Получаем данные пользователя и чата
        try:
            # Используем существующую функцию из base_handlers
            from .base_handlers import get_or_create_user, get_or_create_chat
            
            # Получаем или создаем пользователя и чат
            user = await get_or_create_user(message, user_repository)
            chat = await get_or_create_chat(user, chat_repository)
            
            logger.info(f"🖼️ Пользователь: {user.id}, чат: {chat.id}")
        except Exception as e:
            logger.error(f"🖼️ Ошибка при получении пользователя/чата: {e}", exc_info=True)
            await message.answer("Ошибка при обработке запроса. Пожалуйста, начните с команды /start")
            return

        # Устанавливаем статус "загрузка фото"
        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
        
        try:
            # Генерируем изображение
            logger.info(f"🖼️ Передаем запрос на генерацию изображения: {message.text}")
            response, model = await image_generation_usecase.generate_image_without_switching_chat(user, chat, message.text)
            
            # Проверяем на ошибку rate limit
            if 'error' in response and response['error'] == 'FLOOD_ERROR':
                logger.warning(f"🖼️ Получена ошибка rate limit при генерации изображения")
                await message.answer(response['response']['content'])
                return
                
            # Обработка ответа с изображениями
            if 'response' in response and 'attachments' in response['response'] and response['response']['attachments']:
                logger.info(f"🖼️ Получены изображения от API: {len(response['response']['attachments'])}")
                
                success_count = 0
                for index, attachment in enumerate(response['response']['attachments']):
                    logger.info(f"🖼️ Обработка вложения {index+1}: {json.dumps(attachment, ensure_ascii=False)}")
                    
                    if 'file' in attachment:
                        file_data = attachment['file']
                        logger.info(f"🖼️ Данные файла: {json.dumps(file_data, ensure_ascii=False)}")
                        
                        # Проверяем и получаем URL
                        image_url = None
                        if isinstance(file_data, dict):
                            if file_data.get("url"):
                                image_url = file_data["url"]
                                logger.info(f"🖼️ Получен URL изображения из поля url: {image_url}")
                            elif file_data.get("path"):
                                image_url = f"https://storage.bothub.chat/bothub-storage/{file_data['path']}"
                                logger.info(f"🖼️ Сформирован URL изображения из path: {image_url}")
                        elif isinstance(file_data, str):
                            image_url = file_data
                            logger.info(f"🖼️ Получен URL изображения из строкового значения: {image_url}")
                        
                        if not image_url:
                            logger.error(f"🖼️ Не удалось получить URL изображения из данных: {json.dumps(file_data, ensure_ascii=False)}")
                            await message.answer(f"Ошибка: не удалось получить URL изображения из данных сервера.")
                            continue
                        
                        logger.info(f"🖼️ Финальный URL изображения для скачивания: {image_url}")
                        
                        # Скачиваем изображение
                        image_path = await download_image(image_url)
                        
                        if image_path:
                            # Отправляем изображение
                            try:
                                # Создаем FSInputFile вместо открытия файла
                                photo = FSInputFile(image_path)
                                await message.answer_photo(
                                    photo=photo,
                                    caption=f"Сгенерировано моделью: {model}",
                                    parse_mode="HTML"
                                )
                                logger.info(f"🖼️ Изображение успешно отправлено пользователю")
                                success_count += 1
                                
                                # Удаляем временный файл
                                try:
                                    os.remove(image_path)
                                    logger.info(f"🖼️ Временный файл удален: {image_path}")
                                except Exception as e:
                                    logger.error(f"🖼️ Ошибка при удалении временного файла: {e}")
                            except Exception as e:
                                logger.error(f"🖼️ Ошибка при отправке изображения: {e}")
                                await message.answer(f"Ошибка при отправке изображения: {str(e)}")
                        else:
                            logger.error(f"🖼️ Не удалось скачать изображение: {image_url}")
                            # Не отправляем сообщение о каждом отдельном изображении, чтобы не спамить

                # Отображаем итоговый результат
                if success_count > 0:
                    logger.info(f"🖼️ Успешно отправлено {success_count} из {len(response['response']['attachments'])} изображений")
                else:
                    # Проверяем, содержат ли вложения локальные пути
                    local_paths_detected = False
                    discord_paths_detected = False
                    
                    for attachment in response['response']['attachments']:
                        if 'file' in attachment and isinstance(attachment['file'], dict):
                            url = attachment['file'].get('url', '')
                            if url and "local/images" in url:
                                local_paths_detected = True
                            elif url and "discord" in url:
                                discord_paths_detected = True
                                
                    # Формируем соответствующее сообщение пользователю
                    if local_paths_detected:
                        logger.error(f"🖼️ Изображения доступны только локально на сервере BotHub и не могут быть загружены")
                        await message.answer("⚠️ Изображения были сгенерированы, но доступны только локально на сервере и не могут быть загружены в Telegram. Это связано с настройкой сервера Bothub.")
                    elif discord_paths_detected:
                        logger.error(f"🖼️ Обнаружены ссылки Discord, которые недоступны")
                        await message.answer("⚠️ Изображения были сгенерированы, но ссылки на них недоступны. Возможно, файлы были удалены с сервера. Пожалуйста, попробуйте еще раз.")
                    else:
                        logger.error(f"🖼️ Не удалось отправить ни одного изображения")
                        await message.answer("К сожалению, не удалось загрузить ни одного изображения. Возможно, файлы недоступны на сервере или были удалены. Пожалуйста, попробуйте другой запрос.")
            else:
                # Если нет вложений, отправляем текстовое сообщение
                logger.warning(f"🖼️ Нет вложений в ответе от API")
                content = response.get('response', {}).get('content', 'Не удалось сгенерировать изображение.')
                await message.answer(content)
                
        except Exception as e:
            logger.error(f"🖼️ Ошибка при генерации изображения: {e}", exc_info=True)
            await message.answer(f"Ошибка при генерации изображения: {str(e)}")
        finally:
            # Логируем время выполнения
            end_time = time.time()
            logger.info(f"🖼️ Время обработки запроса на генерацию изображения: {end_time - start_time:.2f} сек")

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

                    # ИСПРАВЛЕНИЕ: Создаем новый чат через usecase
                    await chat_session_usecase.create_new_chat(user, chat)

                    # ВАЖНО: Сохраняем обновленный чат в базе данных
                    await chat_repository.update(chat)
                    logger.info(f"Обновлен чат в БД: {chat.bothub_chat_id}")

                    # ВАЖНО: Сохраняем обновленного пользователя в базе данных
                    await user_repository.update(user)
                    logger.info(f"Обновлен пользователь в БД: bothub_id={user.bothub_id}")

                    model_name = chat.bothub_chat_model or "default"
                    await message.answer(
                        f"✅ Новый чат создан с моделью *{model_name}*.\n\nТеперь вы можете продолжить общение.",
                        parse_mode="Markdown",
                        reply_markup=get_main_keyboard(user, chat)
                    )

                    logger.info(f"Пользователь {user.id} создал новый чат {chat.bothub_chat_id}")
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
                await process_image_generation(message)
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