from typing import Dict, Tuple, Any
import re


class IntentType:
    CHAT = "chat"
    WEB_SEARCH = "web_search"
    IMAGE_GENERATION = "image_generation"


class IntentDetectionService:
    """Сервис для определения намерения пользователя"""

    @staticmethod
    def detect_intent(text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Определяет намерение пользователя на основе текста

        Возвращает:
            Кортеж (тип_намерения, дополнительные_данные)
        """
        text = text.lower().strip()

        # Шаблоны для определения намерения генерации изображения
        image_patterns = [
            r"(сгенерир(уй|овать)|создай|нарисуй|draw|generate|create|paint|picture of|image of|photo of)",
            r"(картинк|изображен|рисун|фото|image|picture|photo|pic|draw)",
            r"(midjourney|dalle|stable diffusion)"
        ]

        # Шаблоны для определения намерения поиска в интернете
        web_search_patterns = [
            r"(найди|поищи|загугли|search|find|google|look up|поиск)",
            r"(в интернете|в сети|онлайн|online|on the web|on the internet)",
            r"(последн(ие|юю) новост|актуальн|current|latest|news|информаци)"
        ]

        # Проверка намерения генерации изображения
        for pattern in image_patterns:
            if re.search(pattern, text):
                return IntentType.IMAGE_GENERATION, {"query": text}

        # Проверка намерения веб-поиска
        for pattern in web_search_patterns:
            if re.search(pattern, text):
                return IntentType.WEB_SEARCH, {"query": text}

        # По умолчанию - обычный чат
        return IntentType.CHAT, {"query": text}