import asyncio
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from src.adapter.repository.message_repository import MessageRepository
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
from src.domain.entity.message import MessageStatus, MessageType
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.lib.clients.bothub_client import BothubClient
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MessageWorker:
    """Воркер для обработки сообщений (аналог PHP CompletedMessageCommand)"""

    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.settings = get_settings()
        self.running = False

        # Инициализируем репозитории
        self.message_repo = MessageRepository()
        self.user_repo = UserRepository()
        self.user_chat_repo = ChatRepository()

        # Инициализируем сервисы
        bothub_client = BothubClient(self.settings)
        bothub_gateway = BothubGateway(bothub_client)
        self.chat_session = ChatSessionUseCase(bothub_gateway)

    async def start(self):
        """Запуск воркера"""
        self.running = True
        logger.info(f"Worker {self.worker_id} started")

        while self.running:
            try:
                await self._process_messages()
                await asyncio.sleep(1)  # Пауза между циклами
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Увеличенная пауза при ошибке

    async def stop(self):
        """Остановка воркера"""
        self.running = False
        logger.info(f"Worker {self.worker_id} stopped")

    async def _process_messages(self):
        """Обработка сообщений"""
        # Находим необработанные сообщения
        messages = await self.message_repo.find_unprocessed_messages(
            worker_id=self.worker_id,
            limit=5
        )

        for message in messages:
            try:
                # Назначаем сообщение воркеру
                assigned = await self.message_repo.assign_to_worker(message.id, self.worker_id)
                if not assigned:
                    # Сообщение уже взято другим воркером
                    continue

                logger.info(f"Worker {self.worker_id} processing message {message.id}")

                # Получаем пользователя и чат
                user = await self.user_repo.find_by_id(message.user_id)
                if not user:
                    logger.error(f"User {message.user_id} not found for message {message.id}")
                    await self.message_repo.mark_error(message.id)
                    continue

                user_chat = await self.user_chat_repo.find_by_user_id_and_chat_index(
                    user.id, message.chat_index
                )
                if not user_chat:
                    logger.error(f"Chat {message.chat_index} not found for user {user.id}")
                    await self.message_repo.mark_error(message.id)
                    continue

                # Обрабатываем сообщение в зависимости от типа
                await self._handle_message_by_type(message, user, user_chat)

                # Отмечаем сообщение как обработанное
                await self.message_repo.mark_processed(message.id)

                logger.info(f"Worker {self.worker_id} completed message {message.id}")

            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}", exc_info=True)
                await self.message_repo.mark_error(message.id)

    async def _handle_message_by_type(self, message, user, user_chat):
        """Обработка сообщения в зависимости от типа"""
        if message.type == MessageType.SEND_MESSAGE:
            # Обычное текстовое сообщение
            response = await self.chat_session.send_message(
                user, user_chat, message.text
            )

            # Увеличиваем счетчик контекста
            if user_chat.context_remember:
                user_chat.increment_context_counter()
                await self.user_chat_repo.update(user_chat)

            # Сохраняем ответ в базу
            # Здесь можно добавить логику сохранения ответа

        elif message.type == MessageType.CREATE_NEW_CHAT:
            # Создание нового чата
            await self.chat_session.create_new_chat(user, user_chat)

        elif message.type == MessageType.RESET_CONTEXT:
            # Сброс контекста
            await self.chat_session.reset_context(user, user_chat)
            user_chat.reset_context_counter()
            await self.user_chat_repo.update(user_chat)

        elif message.type == MessageType.VOICE_MESSAGE:
            # Обработка голосового сообщения
            file_path = message.get_data('file_path')
            if file_path:
                transcribed_text = await self.chat_session.transcribe_voice(
                    user, user_chat, file_path
                )
                # Обновляем текст сообщения транскрибированным текстом
                message.text = transcribed_text
                await self.message_repo.update(message)

        else:
            logger.warning(f"Unknown message type: {message.type}")


class WorkerManager:
    """Менеджер воркеров"""

    def __init__(self, worker_count: int = 3):
        self.worker_count = worker_count
        self.workers: List[MessageWorker] = []
        self.tasks: List[asyncio.Task] = []
        self.cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Запуск всех воркеров"""
        logger.info(f"Starting {self.worker_count} workers")

        # Создаем и запускаем воркеров
        for i in range(self.worker_count):
            worker = MessageWorker(worker_id=i + 1)
            self.workers.append(worker)

            # Запускаем воркера в отдельной задаче
            task = asyncio.create_task(worker.start())
            self.tasks.append(task)

        # Запускаем задачу очистки зависших сообщений
        self.cleanup_task = asyncio.create_task(self._cleanup_stuck_messages())

        logger.info("All workers started")

    async def stop(self):
        """Остановка всех воркеров"""
        logger.info("Stopping all workers")

        # Останавливаем воркеров
        for worker in self.workers:
            await worker.stop()

        # Отменяем задачи
        for task in self.tasks:
            task.cancel()

        if self.cleanup_task:
            self.cleanup_task.cancel()

        # Ждем завершения задач
        await asyncio.gather(*self.tasks, return_exceptions=True)

        logger.info("All workers stopped")

    async def _cleanup_stuck_messages(self):
        """Очистка зависших сообщений"""
        message_repo = MessageRepository()

        while True:
            try:
                # Сбрасываем зависшие сообщения каждые 5 минут
                await asyncio.sleep(300)

                reset_count = await message_repo.reset_stuck_messages(timeout_minutes=30)
                if reset_count > 0:
                    logger.warning(f"Reset {reset_count} stuck messages")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)


# Глобальный менеджер воркеров
worker_manager: Optional[WorkerManager] = None


async def start_workers():
    """Запуск воркеров"""
    global worker_manager

    settings = get_settings()
    worker_manager = WorkerManager(worker_count=settings.WORKER_COUNT)
    await worker_manager.start()


async def stop_workers():
    """Остановка воркеров"""
    global worker_manager

    if worker_manager:
        await worker_manager.stop()
        worker_manager = None