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
    BOTHUB_API_URL: str
    BOTHUB_SECRET_KEY: str

    # Настройки приложения
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Фабричный метод для создания настроек"""
    return Settings()