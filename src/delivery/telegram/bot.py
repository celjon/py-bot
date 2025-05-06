# src/delivery/telegram/bot.py
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties
from src.config.settings import Settings
from src.delivery.telegram.handlers import create_handlers
from src.domain.service.intent_detection import IntentDetectionService
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.account_connection import AccountConnectionUseCase
from src.lib.clients.bothub_client import BothubClient
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository
import logging

logger = logging.getLogger(__name__)

def create_bot(settings: Settings, user_repository=None, chat_repository=None) -> tuple[Bot, Dispatcher]:
    """Фабричный метод для создания бота и диспетчера"""
    # Создаём сессию с кастомным API URL
    session = AiohttpSession(api=TelegramAPIServer.from_base(settings.TELEGRAM_API_URL))

    # Инициализируем бота
    bot = Bot(
        token=settings.TELEGRAM_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode='Markdown')
    )

    # Создаём диспетчер
    dp = Dispatcher()

    # Инициализация клиентов
    bothub_client = BothubClient(settings)

    # Инициализация адаптеров
    bothub_gateway = BothubGateway(bothub_client)

    # Используем переданные репозитории или создаем пустые заглушки
    if user_repository is None:
        import os
        temp_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../data/temp.db')
        os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)
        user_repository = UserRepository(temp_db_path)

    if chat_repository is None:
        import os
        temp_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../data/temp.db')
        os.makedirs(os.path.dirname(temp_db_path), exist_ok=True)
        chat_repository = ChatRepository(temp_db_path)

    # Инициализация сервисов
    intent_detection_service = IntentDetectionService()

    # Инициализация юзкейсов
    chat_session_usecase = ChatSessionUseCase(bothub_gateway)
    account_connection_usecase = AccountConnectionUseCase(bothub_gateway, settings)

    # Создание обработчиков
    handlers_dp = create_handlers(
        chat_session_usecase=chat_session_usecase,
        account_connection_usecase=account_connection_usecase,
        intent_detection_service=intent_detection_service,
        user_repository=user_repository,
        chat_repository=chat_repository
    )

    # Подключаем обработчики к диспетчеру
    logger.info(f"Type of handlers_dp: {type(handlers_dp)}")
    print(f"Type of handlers_dp: {type(handlers_dp)}")
    dp.include_router(handlers_dp)

    logger.info(f"Bot created with custom Telegram API URL: {settings.TELEGRAM_API_URL}")

    return bot, dp