import re
from enum import Enum
from typing import Dict, Tuple, List, Any, Optional


class IntentType(Enum):
    CHAT = "chat"  # Обычное общение с ботом
    WEB_SEARCH = "web_search"  # Поиск информации в интернете
    IMAGE_GENERATION = "image_generation"  # Генерация изображений


class IntentDetectionService:
    """Сервис для определения намерений пользователя на основе его сообщений."""

    def __init__(self):
        # Ключевые слова для определения намерения поиска в интернете
        self.web_search_keywords = [
            r"\b(найди|поищи|загугли|погугли|search|find|google)\b",
            r"\bчто такое\b",
            r"\bкто такой\b",
            r"\bчто значит\b",
            r"\bкак называется\b",
            r"\bинформация о\b",
            r"\bweb[- ]?search\b",
            r"\binfo about\b",
            r"\blook up\b",
            r"\bкогда произошло\b",
            r"\bв каком году\b",
            r"\bсколько лет\b",
            r"\bкакая дата\b",
            r"\bкогда был\b",
            r"\bкогда родился\b",
            r"\bкогда умер\b",
            r"\bгде находится\b",
            r"\bсобытия\b",
            r"\bистория\b",
            r"\bактуальная информация\b",
            r"\bпоследние новости\b",
            r"\bсвежие данные\b",
            r"\bновости\b",
            r"\bкурс\b",
        ]

        # Ключевые слова для определения намерения генерации изображений
        self.image_generation_keywords = [
            r"\b(нарисуй|сгенерируй|создай|изобрази|draw|generate|create|picture|image|imagine|visualize)\b.*\b(картинку|изображение|фото|фотографию|арт)\b",
            r"\bнарисуй\b",
            r"\bсгенерируй\b",
            r"\bсоздай\b",
            r"\bизобрази\b",
            r"\bdraw\b",
            r"\bgenerate image\b",
            r"\bcreate image\b",
            r"\bpicture of\b",
            r"\bvisualize\b",
            r"\bimagine\b",
            r"\bpaint\b",
            r"\billustrate\b",
            r"\bmidjourney\b",
            r"\bdalle\b",
            r"\bdall-e\b",
            r"\bstable diffusion\b",
        ]

        # Контекст предыдущих сообщений и определенных намерений
        self.context = {}

    def detect_intent(self, text: str, user_id: Optional[str] = None,
                      chat_context: Optional[List[Dict[str, Any]]] = None) -> Tuple[IntentType, Dict[str, Any]]:
        """
        Определение намерения пользователя на основе текста сообщения и контекста.

        Args:
            text: Текст сообщения пользователя
            user_id: ID пользователя (для контекстного анализа)
            chat_context: Предыдущие сообщения в чате (для контекстного анализа)

        Returns:
            Tuple[IntentType, Dict[str, Any]]: Тип намерения и дополнительные данные
        """
        # Приводим текст к нижнему регистру для удобства анализа
        text_lower = text.lower()

        # Проверяем на намерение поиска в интернете
        for pattern in self.web_search_keywords:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Определяем запрос для поиска
                search_query = self._extract_search_query(text_lower, pattern)
                return IntentType.WEB_SEARCH, {"query": search_query or text}

        # Проверяем на намерение генерации изображений
        for pattern in self.image_generation_keywords:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Определяем запрос для генерации изображения
                image_prompt = self._extract_image_prompt(text_lower, pattern)
                return IntentType.IMAGE_GENERATION, {"prompt": image_prompt or text}

        # Если не определено специфическое намерение, считаем что это обычный чат
        return IntentType.CHAT, {"message": text}

    def _extract_search_query(self, text: str, pattern: str) -> Optional[str]:
        """
        Извлечение поискового запроса из текста сообщения.
        Пример: "найди информацию о Пушкине" -> "Пушкин"

        Args:
            text: Текст сообщения
            pattern: Шаблон, который соответствует поисковому намерению

        Returns:
            Optional[str]: Извлеченный поисковый запрос или None
        """
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        # Пытаемся извлечь запрос после ключевого слова
        start_pos = match.end()
        query = text[start_pos:].strip()

        # Если запрос есть и он не пустой, возвращаем его
        if query:
            return query

        # Иначе возвращаем весь текст
        return text

    def _extract_image_prompt(self, text: str, pattern: str) -> Optional[str]:
        """
        Извлечение промпта для генерации изображения из текста сообщения.
        Пример: "нарисуй красивый закат над морем" -> "красивый закат над морем"

        Args:
            text: Текст сообщения
            pattern: Шаблон, который соответствует намерению генерации изображения

        Returns:
            Optional[str]: Извлеченный промпт или None
        """
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None

        # Пытаемся извлечь промпт после ключевого слова
        start_pos = match.end()
        prompt = text[start_pos:].strip()

        # Если промпт есть и он не пустой, возвращаем его
        if prompt:
            return prompt

        # Иначе возвращаем весь текст без ключевого слова
        return re.sub(pattern, '', text, flags=re.IGNORECASE).strip()