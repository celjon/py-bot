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
import logging

logger = logging.getLogger(__name__)

# Создаём роутер для aiogram
dp = Router()

def create_handlers(
    chat_session_usecase: ChatSessionUseCase,
    web_search_usecase: WebSearchUseCase,
    image_generation_usecase: ImageGenerationUseCase,
    intent_detection_service: IntentDetectionService,
    user_repository,  # Будет реализовано позже
    chat_repository   # Будет реализовано позже
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
                language_code=message.from_user.language_code
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

    @dp.message(Command("start"))
    async def handle_start_command(message: Message):
        """Обработка команды /start"""
        user = await get_or_create_user(message)

        await message.answer(
            "Привет! Я умный бот, который может:\n\n"
            "🤖 Общаться с вами как ChatGPT\n"
            "🔍 Искать информацию в интернете\n"
            "🎨 Генерировать изображения\n\n"
            "Просто напишите мне, что вы хотите, и я автоматически определю ваше намерение!",
            parse_mode="Markdown"
        )

    @dp.message(Command("reset"))
    async def handle_reset_command(message: Message):
        """Обработка команды /reset для сброса контекста"""
        user = await get_or_create_user(message)
        chat = await get_or_create_chat(user)

        # Сбрасываем счетчик контекста
        chat.context_counter = 0
        await chat_repository.update(chat)

        await message.answer(
            "Контекст сброшен! Теперь я не буду учитывать предыдущие сообщения.",
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

            try:
                if intent_type == IntentType.CHAT:
                    # Обычный чат с ИИ
                    try:
                        response = await chat_session_usecase.send_message(
                            user,
                            chat,
                            message.text,
                            None  # TODO: поддержка файлов
                        )

                        await message.answer(
                            response.get("response", {}).get("content", "Извините, произошла ошибка"),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Error in chat session: {e}", exc_info=True)
                        await message.answer(
                            f"Не удалось получить ответ от чата: {str(e)}",
                            parse_mode="Markdown"
                        )

                elif intent_type == IntentType.WEB_SEARCH:
                    # Поиск в интернете
                    await message.answer(
                        "Ищу информацию в интернете...",
                        parse_mode="Markdown"
                    )

                    try:
                        response = await web_search_usecase.search(
                            user,
                            chat,
                            message.text,
                            None  # TODO: поддержка файлов
                        )

                        await message.answer(
                            response.get("response", {}).get("content", "Извините, я не смог найти информацию"),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Error in web search: {e}", exc_info=True)
                        await message.answer(
                            f"Не удалось выполнить поиск: {str(e)}",
                            parse_mode="Markdown"
                        )

                elif intent_type == IntentType.IMAGE_GENERATION:
                    # Генерация изображения
                    await message.answer(
                        "Генерирую изображение...",
                        parse_mode="Markdown"
                    )

                    try:
                        response = await image_generation_usecase.generate_image(
                            user,
                            chat,
                            message.text,
                            None  # TODO: поддержка файлов
                        )

                        attachments = response.get("response", {}).get("attachments", [])
                        if attachments:
                            for attachment in attachments:
                                if attachment.get("file", {}).get("type") == "IMAGE":
                                    url = attachment.get("file", {}).get("url")
                                    if url:
                                        await message.answer_photo(url)
                                    else:
                                        await message.answer(
                                            "Не удалось получить URL изображения",
                                            parse_mode="Markdown"
                                        )
                        else:
                            await message.answer(
                                "Извините, не удалось сгенерировать изображение",
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.error(f"Error in image generation: {e}", exc_info=True)
                        await message.answer(
                            f"Не удалось сгенерировать изображение: {str(e)}",
                            parse_mode="Markdown"
                        )

                # Сохраняем обновленные данные
                await user_repository.update(user)
                await chat_repository.update(chat)

            except Exception as e:
                logger.error(f"Error processing intent {intent_type}: {e}", exc_info=True)
                await message.answer(
                    f"Извините, произошла ошибка при обработке вашего запроса: {str(e)}",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await message.answer(
                "Извините, произошла ошибка при обработке сообщения",
                parse_mode="Markdown"
            )

    # Возвращаем роутер для aiogram
    return dp