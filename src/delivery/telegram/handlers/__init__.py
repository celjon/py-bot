# src/delivery/telegram/handlers/__init__.py
from aiogram import Router
from .command_handlers import register_command_handlers
from .config_handlers import register_config_handlers
from .account_handlers import register_account_handlers
from .chat_handlers import register_chat_handlers
from .message_handlers import register_message_handlers
from .context_handlers import register_context_handlers


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

    # Регистрируем обработчики текстовых сообщений (ВАЖНО: добавили account_connection_usecase)
    register_message_handlers(
        main_router,
        chat_session_usecase,
        intent_detection_service,
        user_repository,
        chat_repository,
        settings,
        account_connection_usecase  # Добавили этот параметр
    )

    return main_router