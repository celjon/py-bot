# src/domain/usecase/chat_session.py
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ChatSessionUseCase:
    """Юзкейс для работы с чат-сессиями"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """
        Создание нового чата

        Args:
            user: Пользователь
            chat: Чат
            is_image_generation: Флаг для чата с генерацией изображений
        """
        logger.info(f"Создание нового чата для пользователя {user.id}")
        await self.gateway.create_new_chat(user, chat, is_image_generation)

    async def send_message(self, user: User, chat: Chat, message: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Отправка сообщения в чат

        Args:
            user: Пользователь
            chat: Чат
            message: Текст сообщения
            files: Список файлов (опционально)

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        logger.info(f"Отправка сообщения в чат {chat.bothub_chat_id} для пользователя {user.id}")

        try:
            # Получаем доступ к BotHub API через gateway
            return await self.gateway.send_message(user, chat, message, files)
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {str(e)}")
            error_message = str(e)

            if "NOT_ENOUGH_TOKENS" in error_message:
                # Улучшенное сообщение при нехватке токенов
                return {
                    "response": {
                        "content": "⚠️ У вас закончились токены. Пожалуйста, пополните баланс или привяжите существующий аккаунт BotHub с помощью команды /link_account."
                    }
                }
            elif "502 Bad Gateway" in error_message:
                # Если сервер недоступен
                return {
                    "response": {
                        "content": "Извините, в данный момент сервер BotHub недоступен. Пожалуйста, попробуйте позже. Мы работаем над решением проблемы."
                    }
                }
            else:
                # Другие ошибки - общее сообщение
                return {
                    "response": {
                        "content": "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже или обратитесь в поддержку."
                    }
                }

    async def reset_context(self, user: User, chat: Chat) -> None:
        """
        Сброс контекста чата

        Args:
            user: Пользователь
            chat: Чат
        """
        logger.info(f"Сброс контекста чата {chat.bothub_chat_id} для пользователя {user.id}")
        await self.gateway.reset_context(user, chat)
        chat.reset_context_counter()

    async def transcribe_voice(self, user: User, chat: Chat, file_path: str) -> str:
        """
        Транскрибирование голосового сообщения

        Args:
            user: Пользователь
            chat: Чат
            file_path: Путь к аудиофайлу

        Returns:
            str: Транскрибированный текст
        """
        logger.info(f"Транскрибирование голосового сообщения для пользователя {user.id}")

        try:
            # Отправляем запрос на транскрибацию через gateway
            return await self.gateway.transcribe_voice(user, chat, file_path)
        except Exception as e:
            logger.error(f"Ошибка при транскрибировании голосового сообщения: {e}", exc_info=True)
            return "Не удалось распознать голосовое сообщение. Пожалуйста, попробуйте еще раз."