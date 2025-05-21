from aiogram import Router
from .command_handlers import register_command_handlers
from .config_handlers import register_config_handlers
from .account_handlers import register_account_handlers
from .chat_handlers import register_chat_handlers
from .message_handlers import register_message_handlers
from .context_handlers import register_context_handlers
from .image_handlers import register_image_handlers


def setup_handlers(
        chat_session_usecase,
        account_connection_usecase,
        intent_detection_service,
        user_repository,
        chat_repository,
        settings
) -> Router:
    """Настройка всех обработчиков и их объединение в один роутер"""

    # Создаем главный роутер
    main_router = Router()

    # Регистрируем обработчики базовых команд
    register_command_handlers(
        main_router,
        chat_session_usecase,
        user_repository,
        chat_repository
    )

    # Регистрируем обработчики команд конфигурации
    register_config_handlers(
        main_router,
        user_repository,
        chat_repository
    )

    # Регистрируем обработчики команд аккаунта
    register_account_handlers(
        main_router,
        account_connection_usecase,
        user_repository,
        chat_repository
    )

    # Регистрируем обработчики контекста
    register_context_handlers(
        main_router,
        chat_session_usecase,
        user_repository,
        chat_repository
    )

    # Регистрируем обработчики команд чата
    register_chat_handlers(
        main_router,
        chat_session_usecase,
        user_repository,
        chat_repository
    )

    # Создаем экземпляр UseCase для генерации изображений
    image_generation_usecase = get_image_generation_usecase()

    # Регистрируем обработчики генерации изображений
    register_image_handlers(
        main_router,
        image_generation_usecase,
        user_repository,
        chat_repository
    )

    # Регистрируем обработчики текстовых сообщений
    register_message_handlers(
        main_router,
        chat_session_usecase,
        image_generation_usecase,
        intent_detection_service,
        user_repository,
        chat_repository,
        settings
    )

    return main_router


# Функция для получения экземпляра ImageGenerationUseCase
def get_image_generation_usecase():
    """Получение экземпляра ImageGenerationUseCase"""
    from src.adapter.gateway.bothub_gateway import BothubGateway
    from src.lib.clients.bothub_client import BothubClient
    from src.config.settings import get_settings
    from src.domain.usecase.image_generation import ImageGenerationUseCase

    settings = get_settings()
    bothub_client = BothubClient(settings)
    bothub_gateway = BothubGateway(bothub_client)

    return ImageGenerationUseCase(bothub_gateway)


# Функция для получения экземпляра ModelSelectionUseCase
def get_model_selection_usecase():
    """Получение экземпляра ModelSelectionUseCase"""
    from src.adapter.gateway.bothub_gateway import BothubGateway
    from src.lib.clients.bothub_client import BothubClient
    from src.config.settings import get_settings
    from src.domain.usecase.model_selection import ModelSelectionUseCase

    settings = get_settings()
    bothub_client = BothubClient(settings)
    bothub_gateway = BothubGateway(bothub_client)

    return ModelSelectionUseCase(bothub_gateway)