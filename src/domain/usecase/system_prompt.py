from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SystemPromptUseCase:
    """Юзкейс для работы с системными промптами"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def set_system_prompt(self, user: User, chat: Chat, prompt: str) -> None:
        """
        Установка системного промпта для чата

        Args:
            user: Пользователь
            chat: Чат
            prompt: Текст системного промпта
        """
        logger.info(f"Установка системного промпта для пользователя {user.id}")

        # Записываем промпт в чат
        chat.system_prompt = prompt

        # Если чат еще не создан, создаем его
        if not chat.bothub_chat_id:
            await self.gateway.create_new_chat(user, chat)
            return

        # Применяем системный промпт для чата
        try:
            await self.gateway.save_system_prompt(user, chat)
            logger.info(f"Системный промпт успешно установлен для чата {chat.bothub_chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при установке системного промпта: {e}")
            raise Exception(f"Не удалось установить системный промпт: {e}")

    async def reset_system_prompt(self, user: User, chat: Chat) -> None:
        """
        Сброс системного промпта для чата

        Args:
            user: Пользователь
            chat: Чат
        """
        logger.info(f"Сброс системного промпта для пользователя {user.id}")

        # Очищаем промпт в чате
        chat.system_prompt = ""

        # Если чат еще не создан, просто выходим
        if not chat.bothub_chat_id:
            return

        # Применяем пустой системный промпт для чата
        try:
            await self.gateway.save_system_prompt(user, chat)
            logger.info(f"Системный промпт успешно сброшен для чата {chat.bothub_chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при сбросе системного промпта: {e}")
            raise Exception(f"Не удалось сбросить системный промпт: {e}")

    async def get_system_prompt(self, chat: Chat) -> str:
        """
        Получить текущий системный промпт чата

        Args:
            chat: Чат

        Returns:
            str: Текст системного промпта
        """
        return chat.system_prompt