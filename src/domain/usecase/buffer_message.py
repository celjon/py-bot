# src/domain/usecase/buffer_message.py

from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, Optional, List
import logging
from src.lib.utils.file_utils import download_file
import os

logger = logging.getLogger(__name__)


class BufferMessageUseCase:
    """Юзкейс для работы с буфером сообщений"""

    def __init__(self, gateway: BothubGateway):
        self.gateway = gateway

    async def add_to_buffer(self, user: User, chat: Chat, text: Optional[str] = None,
                            file_url: Optional[str] = None, file_name: Optional[str] = None) -> None:
        """
        Добавление сообщения в буфер

        Args:
            user: Пользователь
            chat: Чат
            text: Текст сообщения
            file_url: URL файла
            file_name: Имя файла
        """
        logger.info(f"Добавление сообщения в буфер для пользователя {user.id}")

        # Обрабатываем файл, если он есть
        local_file_name = None
        display_file_name = file_name
        if file_url:
            try:
                # Скачиваем файл
                local_file_path = await download_file(file_url, file_name)
                local_file_name = os.path.basename(local_file_path)
                logger.info(f"Файл {local_file_name} успешно скачан в буфер")
            except Exception as e:
                logger.error(f"Ошибка при скачивании файла: {e}")
                raise Exception(f"Не удалось скачать файл: {e}")

        # Добавляем в буфер
        chat.add_to_buffer(text, local_file_name, display_file_name)

        logger.info(f"Сообщение успешно добавлено в буфер")

    async def send_buffer(self, user: User, chat: Chat) -> Dict[str, Any]:
        """
        Отправка буфера сообщений

        Args:
            user: Пользователь
            chat: Чат

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        logger.info(f"Отправка буфера сообщений для пользователя {user.id}")

        # Проверяем, что буфер не пустой
        if not chat.buffer or 'messages' not in chat.buffer or not chat.buffer['messages']:
            logger.warning("Буфер пуст, нечего отправлять")
            return {"response": {"content": "Буфер пуст, нечего отправлять"}}

        # Формируем сообщение и список файлов из буфера
        message_text = ""
        files = []

        for msg in chat.buffer['messages']:
            if 'text' in msg and msg['text']:
                if message_text:
                    message_text += "\n\n"
                message_text += msg['text']

            if 'fileName' in msg and msg['fileName']:
                files.append(msg['fileName'])

        # Отправляем собранные данные
        try:
            if not message_text and not files:
                return {"response": {"content": "Буфер не содержит ни текста, ни файлов"}}

            # Если нет текста, но есть файлы, добавляем стандартное сообщение
            if not message_text and files:
                message_text = "Анализ файлов из буфера:"

            # Отправляем запрос в BotHub
            result = await self.gateway.send_message(user, chat, message_text, files)

            # Очищаем буфер после успешной отправки
            chat.refresh_buffer()

            return result
        except Exception as e:
            logger.error(f"Ошибка при отправке буфера: {e}")
            raise Exception(f"Не удалось отправить буфер: {e}")

    def clear_buffer(self, chat: Chat) -> None:
        """
        Очистка буфера сообщений

        Args:
            chat: Чат
        """
        logger.info(f"Очистка буфера сообщений для чата {chat.id}")
        chat.refresh_buffer()