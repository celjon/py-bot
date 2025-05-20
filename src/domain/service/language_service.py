# src/domain/service/language_service.py
import json
import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class LanguageService:
    """Сервис для работы с локализациями (аналог PHP LanguageService)"""

    # Словари с переводами
    translations = {
        "en": {
            "accounts_merged": "✅ Your accounts have been successfully linked!\n\nEmail: **{}**\n\nYou can use all bot functions with your connected account.",
            "present_done": "✅ The tokens have been successfully sent!",
            "present_done_email": "✅ The tokens have been successfully sent to the specified email!",
            "present_resend_notification": "The recipient will receive a notification about the gift when they launch the bot.",
            "error_unknown_error": "❌ An unknown error occurred. Please try again."
        },
        "ru": {
            "accounts_merged": "✅ Ваши аккаунты успешно связаны!\n\nEmail: **{}**\n\nВы можете использовать все функции бота с подключенным аккаунтом.",
            "present_done": "✅ Токены успешно отправлены!",
            "present_done_email": "✅ Токены успешно отправлены на указанный email!",
            "present_resend_notification": "Получатель получит уведомление о подарке при запуске бота.",
            "error_unknown_error": "❌ Произошла неизвестная ошибка. Пожалуйста, попробуйте снова."
        }
    }

    def __init__(self, language_code: str = "en"):
        """
        Инициализация сервиса локализации

        Args:
            language_code: Код языка пользователя (en, ru)
        """
        self.language_code = self._normalize_language_code(language_code)

    def _normalize_language_code(self, code: str) -> str:
        """
        Нормализация кода языка

        Args:
            code: Код языка

        Returns:
            str: Нормализованный код языка (en или ru)
        """
        if not code or len(code) < 2:
            return "en"

        # Берем первые два символа в нижнем регистре
        code = code[:2].lower()

        # Поддерживаемые языки
        if code in ["ru", "uk", "be", "kk"]:
            return "ru"

        # По умолчанию английский
        return "en"

    def get_string(self, key: str, params: List[Any] = None) -> str:
        """
        Получить локализованную строку с подстановкой параметров

        Args:
            key: Ключ строки
            params: Параметры для замены

        Returns:
            str: Локализованная строка
        """
        # Получаем язык
        lang = self.language_code

        # Получаем строку
        if lang in self.translations and key in self.translations[lang]:
            string = self.translations[lang][key]
        else:
            # Пробуем английский, если нет перевода
            string = self.translations["en"].get(key, f"[{key}]")

        # Форматируем строку с параметрами
        if params:
            try:
                return string.format(*params)
            except Exception as e:
                logger.error(f"Ошибка форматирования строки {key}: {e}")
                return string

        return string