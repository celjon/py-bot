import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения"""

    # Telegram Bot API
    TELEGRAM_TOKEN: str
    TELEGRAM_API_URL: str = "http://localhost:8081"  # URL для локального Telegram Bot API
    API_ID: str
    API_HASH: str

    # BotHub API
    BOTHUB_WEBHOOK_SECRET_KEY: str
    BOTHUB_API_URL: str
    BOTHUB_SECRET_KEY: str
    BOTHUB_WEB_URL: str = "https://bothub.chat"  # URL веб-интерфейса BotHub
    WEBHOOK_URL: str

    # PostgreSQL Database
    DATABASE_URL: str
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123"
    POSTGRES_DB: str = "dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433

    # Redis (для очередей и кэша)
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Настройки приложения
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Настройки воркеров
    WORKER_COUNT: int = 3
    WORKER_TIMEOUT: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __post_init__(self):
        """Дополнительная обработка после инициализации"""
        # Если DATABASE_URL не задан, создаем его из компонентов
        if not hasattr(self, 'DATABASE_URL') or not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )


def get_settings() -> Settings:
    """Фабричный метод для создания настроек"""
    return Settings()