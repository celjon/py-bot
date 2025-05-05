# src/delivery/telegram/handlers.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums.chat_action import ChatAction
from src.domain.service.intent_detection import IntentDetectionService, IntentType
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.account_connection import AccountConnectionUseCase
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
import logging

logger = logging.getLogger(__name__)

# Создаём роутер для aiogram
dp = Router()

def create_handlers(
        chat_session_usecase: ChatSessionUseCase,
        account_connection_usecase: AccountConnectionUseCase,  # Новый параметр
        intent_detection_service: IntentDetectionService,
        user_repository: UserRepository,
        chat_repository: ChatRepository
):
    """Фабричный метод для создания обработчиков сообщений Telegram"""

    @dp.message(Command("link_account"))
    async def handle_link_account_command(message: Message):
        """Обработка команды /link_account для привязки аккаунта"""
        try:
            user = await get_or_create_user(message)

            # Если у пользователя уже есть email, значит аккаунт уже подключен
            if user.email:
                await message.answer("Ваш аккаунт Telegram уже привязан к аккаунту BotHub.")
                return

            try:
                # Генерируем ссылку для подключения
                link = await account_connection_usecase.generate_connection_link(user)

                # Отправляем сообщение с ссылкой, избегая использования Markdown
                await message.answer(
                    f"Для привязки вашего Telegram к существующему аккаунту BotHub, перейдите по ссылке:\n\n{link}\n\nПосле привязки вы сможете использовать ваши токены из аккаунта BotHub.")
            except Exception as link_error:
                # Если не удалось сгенерировать ссылку, предлагаем альтернативный способ
                web_url = settings.BOTHUB_WEB_URL or "https://bothub.chat"

                await message.answer(
                    f"Не удалось сгенерировать ссылку для привязки ({str(link_error)}). \n\n"
                    f"Вы можете вручную привязать аккаунт:\n"
                    f"1) Войдите в аккаунт на сайте {web_url}\n"
                    f"2) Перейдите в настройки профиля\n"
                    f"3) Найдите раздел 'Подключенные аккаунты'\n"
                    f"4) Добавьте Telegram и следуйте инструкциям"
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке команды link_account: {e}", exc_info=True)
            await message.answer("Не удалось обработать команду. Попробуйте позже.")

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
            logger.error(f"Ошибка обработки команды /start: {e}", exc_info=True)
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
            logger.error(f"Ошибка сброса контекста: {e}", exc_info=True)
            await message.answer(
                "❌ Не удалось сбросить контекст. Попробуйте еще раз.",
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

            # Для начала просто отправляем сообщение в нейросеть, без определения намерений
            try:
                response = await chat_session_usecase.send_message(
                    user,
                    chat,
                    message.text,
                    None  # Пока без файлов
                )

                content = response.get("response", {}).get("content", "Извините, произошла ошибка")
                await send_long_message(message, content)

                # Если есть счетчик капсов, добавляем его
                if "tokens" in response:
                    caps_text = f"👾 -{response['tokens']} caps"
                    await message.answer(caps_text)

            except Exception as e:
                logger.error(f"Ошибка в сессии чата: {e}", exc_info=True)
                await message.answer(
                    f"❌ Не удалось получить ответ от чата: {str(e)}",
                    parse_mode="Markdown"
                )

            # Сохраняем обновленные данные
            await user_repository.update(user)
            await chat_repository.update(chat)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
            await message.answer(
                "❌ Извините, произошла ошибка при обработке сообщения",
                parse_mode="Markdown"
            )

    # Возвращаем роутер для aiogram
    return dp