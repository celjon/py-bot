from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction
from src.domain.service.intent_detection import IntentDetectionService, IntentType
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.web_search import WebSearchUseCase
from src.domain.usecase.image_generation import ImageGenerationUseCase
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
import logging
import re

logger = logging.getLogger(__name__)

# Создаём роутер для aiogram
dp = Router()


def create_handlers(
        chat_session_usecase: ChatSessionUseCase,
        web_search_usecase: WebSearchUseCase,
        image_generation_usecase: ImageGenerationUseCase,
        intent_detection_service: IntentDetectionService,
        user_repository: UserRepository,
        chat_repository: ChatRepository
):
    """Фабричный метод для создания обработчиков сообщений Telegram"""

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

    async def get_or_create_chat(user: User) -> Chat:
        """Получение или создание чата для пользователя"""
        chat = await chat_repository.find_by_user_id_and_chat_index(
            user.id,
            user.current_chat_index
        )

        if not chat:
            chat = Chat(
                id=0,  # Временный ID, будет заменён после сохранения
                user_id=user.id,
                chat_index=user.current_chat_index
            )
            chat_id = await chat_repository.save(chat)
            chat.id = chat_id

        return chat

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

    @dp.message(Command("start"))
    async def handle_start_command(message: Message):
        """Обработка команды /start"""
        try:
            user = await get_or_create_user(message)
            # Проверяем наличие реферального кода
            if message.text and len(message.text.split()) > 1:
                user.referral_code = message.text.split()[1]
                await user_repository.update(user)

            await message.answer(
                "👋 Привет! Я BotHub, умный ассистент на базе нейросетей.\n\n"
                "✨ Я могу:\n"
                "📝 Общаться с вами, отвечать на вопросы\n"
                "🔍 Искать информацию в интернете\n"
                "🎨 Генерировать изображения\n\n"
                "Просто напишите мне, что вы хотите, и я автоматически определю ваше намерение!\n\n"
                "Полезные команды:\n"
                "/reset - сбросить контекст разговора\n"
                "/help - получить справку",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error processing /start command: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке команды",
                parse_mode="Markdown"
            )

    @dp.message(Command("reset"))
    async def handle_reset_command(message: Message):
        """Обработка команды /reset для сброса контекста"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Сбрасываем счетчик контекста и контекст на сервере BotHub
            await chat_session_usecase.reset_context(user, chat)
            await chat_repository.update(chat)

            await message.answer(
                "🔄 Контекст разговора сброшен! Теперь я не буду учитывать предыдущие сообщения.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error resetting context: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    @dp.message(Command("help"))
    async def handle_help_command(message: Message):
        """Обработка команды /help"""
        try:
            await message.answer(
                "🔍 **Как пользоваться ботом:**\n\n"
                "1. **Для обычного общения** просто напишите свой вопрос или сообщение\n"
                "   Например: *\"Расскажи о квантовой физике\"*\n\n"
                "2. **Для поиска в интернете** используйте слова: найди, поищи, загугли\n"
                "   Например: *\"Найди информацию о последних новостях\"*\n\n"
                "3. **Для генерации изображений** используйте слова: нарисуй, сгенерируй, создай\n"
                "   Например: *\"Нарисуй красивый закат над океаном\"*\n\n"
                "📋 **Полезные команды:**\n"
                "/reset - сбросить контекст разговора\n"
                "/help - получить эту справку",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error processing /help command: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке команды",
                parse_mode="Markdown"
            )

    @dp.message(Command("continue"))
    async def handle_continue_command(message: Message):
        """Обработка команды /continue для продолжения контекста"""
        try:
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Убеждаемся, что используется модель, поддерживающая контекст
            if not chat.bothub_chat_model or not chat.context_remember:
                await message.answer(
                    "❌ Команда /continue доступна только для моделей с поддержкой контекста.",
                    parse_mode="Markdown"
                )
                return

            # Отправляем запрос на продолжение
            await message.chat.do(ChatAction.TYPING)
            prompt = "Продолжай" if user.language_code == "ru" else "Continue"

            response = await chat_session_usecase.send_message(
                user,
                chat,
                prompt,
                None
            )

            content = response.get("response", {}).get("content", "Извините, произошла ошибка")
            await send_long_message(message, content)

            # Если есть счетчик капсов, добавляем его
            if "tokens" in response:
                caps_text = f"👾 -{response['tokens']} caps"
                await message.answer(caps_text)

        except Exception as e:
            logger.error(f"Error processing /continue command: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось продолжить генерацию. Попробуйте еще раз.",
                parse_mode="Markdown"
            )

    @dp.message(F.text)
    async def handle_text_message(message: Message):
        """Обработка текстовых сообщений"""
        try:
            # Сообщаем пользователю, что бот печатает
            await message.chat.do(ChatAction.TYPING)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Определяем намерение пользователя
            intent_type, intent_data = intent_detection_service.detect_intent(message.text)
            logger.info(f"Detected intent: {intent_type.value} for message: {message.text[:50]}...")

            if intent_type == IntentType.CHAT:
                # Обычный чат с ИИ
                await message.chat.do(ChatAction.TYPING)
                try:
                    response = await chat_session_usecase.send_message(
                        user,
                        chat,
                        message.text,
                        None  # TODO: поддержка файлов
                    )

                    content = response.get("response", {}).get("content", "Извините, произошла ошибка")

                    # Проверяем на наличие формул (будет реализовано позже)
                    if chat.formula_to_image:
                        # TODO: Обработка формул
                        pass

                    await send_long_message(message, content)

                    # Если есть счетчик капсов, добавляем его
                    if "tokens" in response:
                        caps_text = f"👾 -{response['tokens']} caps"
                        await message.answer(caps_text)

                        # Добавление подсказок о контексте
                        if chat.context_remember and chat.context_counter > 0 and chat.context_counter % 2 == 0:
                            context_hint = "Вы можете использовать /continue для продолжения или /reset для сброса контекста."
                            await message.answer(context_hint)

                except Exception as e:
                    logger.error(f"Error in chat session: {e}", exc_info=True)
                    await message.answer(
                        f"❌ Не удалось получить ответ от чата: {str(e)}",
                        parse_mode="Markdown"
                    )

            elif intent_type == IntentType.WEB_SEARCH:
                # Поиск в интернете
                await message.answer(
                    "🔍 Ищу информацию в интернете...",
                    parse_mode="Markdown"
                )
                await message.chat.do(ChatAction.TYPING)

                try:
                    response = await web_search_usecase.search(
                        user,
                        chat,
                        intent_data.get("query", message.text),
                        None  # TODO: поддержка файлов
                    )

                    content = response.get("response", {}).get("content", "Извините, я не смог найти информацию")
                    await send_long_message(message, content)

                    # Если есть счетчик капсов, добавляем его
                    if "tokens" in response:
                        caps_text = f"👾 -{response['tokens']} caps"
                        await message.answer(caps_text)

                except Exception as e:
                    logger.error(f"Error in web search: {e}", exc_info=True)
                    await message.answer(
                        f"❌ Не удалось выполнить поиск: {str(e)}",
                        parse_mode="Markdown"
                    )

            elif intent_type == IntentType.IMAGE_GENERATION:
                # Генерация изображения
                await message.answer(
                    "🎨 Генерирую изображение...",
                    parse_mode="Markdown"
                )

                try:
                    prompt = intent_data.get("prompt", message.text)

                    # Проверка запроса на английском языке (некоторые модели требуют это)
                    if not re.search(r'[a-zA-Z]', prompt):
                        await message.answer(
                            "ℹ️ Добавляю в запрос английский перевод для лучшего результата...",
                            parse_mode="Markdown"
                        )
                        prompt += "\n\nTranslate the above to English"

                    response = await image_generation_usecase.generate_image(
                        user,
                        chat,
                        prompt,
                        None  # TODO: поддержка файлов
                    )

                    attachments = response.get("response", {}).get("attachments", [])
                    if attachments:
                        for attachment in attachments:
                            if attachment.get("file", {}).get("type") == "IMAGE":
                                url = attachment.get("file", {}).get("url")
                                if not url and attachment.get("file", {}).get("path"):
                                    url = f"https://storage.bothub.chat/bothub-storage/{attachment.get('file', {}).get('path')}"

                                if url:
                                    await message.answer_photo(url)

                                    # Если есть кнопки, добавляем их
                                    buttons = attachment.get("buttons", [])
                                    mj_buttons = [b for b in buttons if b.get("type") == "MJ_BUTTON"]
                                    if mj_buttons:
                                        # TODO: Добавить поддержку кнопок Midjourney
                                        pass
                                else:
                                    await message.answer(
                                        "❌ Не удалось получить URL изображения",
                                        parse_mode="Markdown"
                                    )
                    else:
                        await message.answer(
                            "❌ Извините, не удалось сгенерировать изображение",
                            parse_mode="Markdown"
                        )

                    # Если есть счетчик капсов, добавляем его
                    if "tokens" in response:
                        caps_text = f"👾 -{response['tokens']} caps"
                        await message.answer(caps_text)

                except Exception as e:
                    logger.error(f"Error in image generation: {e}", exc_info=True)
                    await message.answer(
                        f"❌ Не удалось сгенерировать изображение: {str(e)}",
                        parse_mode="Markdown"
                    )

            # Сохраняем обновленные данные
            await user_repository.update(user)
            await chat_repository.update(chat)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке сообщения",
                parse_mode="Markdown"
            )

    @dp.message(F.voice)
    async def handle_voice_message(message: Message):
        """Обработка голосовых сообщений"""
        try:
            # Сообщаем пользователю, что бот обрабатывает аудио
            await message.chat.do(ChatAction.RECORD_VOICE)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Скачиваем голосовое сообщение
            file_id = message.voice.file_id
            file = await message.bot.get_file(file_id)
            file_path = file.file_path

            # Проверяем наличие токена
            if not message.bot.token:
                logger.error("Bot token is missing")
                await message.answer("❌ Ошибка: токен бота отсутствует", parse_mode="Markdown")
                return

            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

            await message.answer(
                "🎤 Обрабатываю голосовое сообщение...",
                parse_mode="Markdown"
            )

            # Транскрибируем голосовое сообщение
            try:
                transcribed_text = await chat_session_usecase.transcribe_voice(user, chat, file_url)

                # Отправляем пользователю распознанный текст
                await message.answer(
                    f"📝 Распознанный текст:\n\n{transcribed_text}",
                    parse_mode="Markdown"
                )

                # Теперь обрабатываем текст как обычное сообщение, определяя намерение
                intent_type, intent_data = intent_detection_service.detect_intent(transcribed_text)

                await message.chat.do(ChatAction.TYPING)

                if intent_type == IntentType.CHAT:
                    response = await chat_session_usecase.send_message(user, chat, transcribed_text)
                    content = response.get("response", {}).get("content", "Извините, произошла ошибка")
                    await send_long_message(message, content)

                    # Если есть счетчик капсов, добавляем его
                    if "tokens" in response:
                        caps_text = f"👾 -{response['tokens']} caps"
                        await message.answer(caps_text)

                elif intent_type == IntentType.WEB_SEARCH:
                    await message.answer("🔍 Ищу информацию в интернете...", parse_mode="Markdown")
                    response = await web_search_usecase.search(user, chat, intent_data.get("query", transcribed_text))
                    content = response.get("response", {}).get("content", "Извините, я не смог найти информацию")
                    await send_long_message(message, content)

                    # Если есть счетчик капсов, добавляем его
                    if "tokens" in response:
                        caps_text = f"👾 -{response['tokens']} caps"
                        await message.answer(caps_text)

                elif intent_type == IntentType.IMAGE_GENERATION:
                    await message.answer("🎨 Генерирую изображение...", parse_mode="Markdown")
                    response = await image_generation_usecase.generate_image(user, chat, intent_data.get("prompt",
                                                                                                         transcribed_text))

                    attachments = response.get("response", {}).get("attachments", [])
                    if attachments:
                        for attachment in attachments:
                            if attachment.get("file", {}).get("type") == "IMAGE":
                                url = attachment.get("file", {}).get("url")
                                if not url and attachment.get("file", {}).get("path"):
                                    url = f"https://storage.bothub.chat/bothub-storage/{attachment.get('file', {}).get('path')}"

                                if url:
                                    await message.answer_photo(url)

                                    # Если есть счетчик капсов, добавляем его
                                    if "tokens" in response:
                                        caps_text = f"👾 -{response['tokens']} caps"
                                        await message.answer(caps_text)
                                else:
                                    await message.answer("❌ Не удалось получить URL изображения", parse_mode="Markdown")
                    else:
                        await message.answer("❌ Извините, не удалось сгенерировать изображение", parse_mode="Markdown")

                # Сохраняем обновленные данные
                await user_repository.update(user)
                await chat_repository.update(chat)

            except Exception as e:
                logger.error(f"Error transcribing voice message: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось распознать голосовое сообщение. Попробуйте отправить текстовое сообщение.",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error processing voice message: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке голосового сообщения",
                parse_mode="Markdown"
            )

    @dp.message(F.photo)
    async def handle_photo_message(message: Message):
        """Обработка фотографий"""
        try:
            # Сообщаем пользователю, что бот обрабатывает фото
            await message.chat.do(ChatAction.UPLOAD_PHOTO)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем фото максимального размера
            photo = message.photo[-1]
            file_id = photo.file_id
            file = await message.bot.get_file(file_id)
            file_path = file.file_path

            # Проверяем наличие токена
            if not message.bot.token:
                logger.error("Bot token is missing")
                await message.answer("❌ Ошибка: токен бота отсутствует", parse_mode="Markdown")
                return

            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

            # Получаем описание к фото, если есть
            caption = message.caption or "Опиши что на этом изображении"

            await message.answer(
                "🖼️ Обрабатываю изображение...",
                parse_mode="Markdown"
            )

            # Отправляем изображение с текстом на обработку
            try:
                await message.chat.do(ChatAction.TYPING)
                response = await chat_session_usecase.send_message(user, chat, caption, [file_url])

                content = response.get("response", {}).get("content", "Извините, не удалось обработать изображение")
                await send_long_message(message, content)

                # Если в ответе есть сгенерированное изображение, отправляем его
                attachments = response.get("response", {}).get("attachments", [])
                if attachments:
                    for attachment in attachments:
                        if attachment.get("file", {}).get("type") == "IMAGE":
                            url = attachment.get("file", {}).get("url")
                            if not url and attachment.get("file", {}).get("path"):
                                url = f"https://storage.bothub.chat/bothub-storage/{attachment.get('file', {}).get('path')}"

                            if url:
                                await message.answer_photo(url)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

                # Сохраняем обновленные данные
                await user_repository.update(user)
                await chat_repository.update(chat)

            except Exception as e:
                logger.error(f"Error processing photo: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать изображение. Пожалуйста, попробуйте еще раз.",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error processing photo message: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке фотографии",
                parse_mode="Markdown"
            )

    @dp.message(F.document)
    async def handle_document_message(message: Message):
        """Обработка документов"""
        try:
            # Сообщаем пользователю, что бот обрабатывает документ
            await message.chat.do(ChatAction.UPLOAD_DOCUMENT)

            # Получаем или создаём пользователя и его текущий чат
            user = await get_or_create_user(message)
            chat = await get_or_create_chat(user)

            # Получаем документ
            document = message.document
            file_id = document.file_id
            file_name = document.file_name
            mime_type = document.mime_type

            # Проверяем, что тип файла поддерживается
            supported_mime_types = [
                'text/plain', 'text/html', 'text/csv', 'text/markdown',
                'application/pdf', 'application/json',
                'image/jpeg', 'image/png', 'image/gif', 'image/webp'
            ]

            if mime_type not in supported_mime_types:
                await message.answer(
                    f"⚠️ Тип файла {mime_type} не поддерживается. Поддерживаемые типы: текстовые файлы, PDF, изображения.",
                    parse_mode="Markdown"
                )
                return

            # Скачиваем файл
            file = await message.bot.get_file(file_id)
            file_path = file.file_path

            # Проверяем наличие токена
            if not message.bot.token:
                logger.error("Bot token is missing")
                await message.answer("❌ Ошибка: токен бота отсутствует", parse_mode="Markdown")
                return

            file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_path}"

            # Получаем описание к документу, если есть
            caption = message.caption or f"Проанализируй содержимое этого файла {file_name}"

            await message.answer(
                f"📄 Обрабатываю документ {file_name}...",
                parse_mode="Markdown"
            )

            # Отправляем документ с текстом на обработку
            try:
                await message.chat.do(ChatAction.TYPING)
                response = await chat_session_usecase.send_message(user, chat, caption, [file_url])

                content = response.get("response", {}).get("content", "Извините, не удалось обработать документ")
                await send_long_message(message, content)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

                # Сохраняем обновленные данные
                await user_repository.update(user)
                await chat_repository.update(chat)

            except Exception as e:
                logger.error(f"Error processing document: {e}", exc_info=True)
                await message.answer(
                    "❌ Не удалось обработать документ. Пожалуйста, попробуйте еще раз.",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error processing document message: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке документа",
                parse_mode="Markdown"
            )

    # Возвращаем роутер для aiogram
    return dp