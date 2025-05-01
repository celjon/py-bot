from telebot.async_telebot import AsyncTeleBot
from src.config.settings import Settings
from src.delivery.telegram.handlers import create_handlers
from src.domain.service.intent_detection import IntentDetectionService
from src.domain.usecase.chat_session import ChatSessionUseCase
from src.domain.usecase.web_search import WebSearchUseCase
from src.domain.usecase.image_generation import ImageGenerationUseCase
from src.lib.clients.bothub_client import BothubClient
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.adapter.repository.user_repository import UserRepository
from src.adapter.repository.chat_repository import ChatRepository


def create_bot(settings: Settings):
    """Фабричный метод для создания бота"""
    # Инициализация бота с настройками
    bot = AsyncTeleBot(
        settings.TELEGRAM_TOKEN,
        parse_mode='Markdown'
    )

    # Если у нас есть кастомный URL API, попытаемся установить его
    if hasattr(bot, 'api_url') and settings.TELEGRAM_API_URL:
        bot.api_url = settings.TELEGRAM_API_URL
    elif hasattr(bot, 'server') and settings.TELEGRAM_API_URL:
        bot.server = settings.TELEGRAM_API_URL

    # Инициализация клиентов
    bothub_client = BothubClient(settings)

    # Инициализация адаптеров
    bothub_gateway = BothubGateway(bothub_client)
    user_repository = UserRepository()
    chat_repository = ChatRepository()

    # Инициализация сервисов
    intent_detection_service = IntentDetectionService()

    # Инициализация юзкейсов
    chat_session_usecase = ChatSessionUseCase(bothub_gateway)
    web_search_usecase = WebSearchUseCase(bothub_gateway)
    image_generation_usecase = ImageGenerationUseCase(bothub_gateway)

    # Создание обработчиков
    create_handlers(
        bot,
        chat_session_usecase,
        web_search_usecase,
        image_generation_usecase,
        intent_detection_service,
        user_repository,
        chat_repository
    )

    return bot