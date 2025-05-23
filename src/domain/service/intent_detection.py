import re
from enum import Enum
from typing import Dict, Tuple, List, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


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

        # Набор обнаруженных ключевых слов для логирования и улучшения
        self.detected_keywords = set()

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

        # Сохраняем обнаруженные ключевые слова для улучшения сервиса
        detected_keywords = set()

        # Проверяем на намерение поиска в интернете
        for pattern in self.web_search_keywords:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Добавляем найденное ключевое слово для анализа
                matched = re.search(pattern, text_lower, re.IGNORECASE)
                detected_keywords.add(matched.group(0))

                # Определяем запрос для поиска
                search_query = self._extract_search_query(text_lower, pattern)
                logger.info(f"Detected web search intent with keywords: {detected_keywords}")
                return IntentType.WEB_SEARCH, {"query": search_query or text,
                                               "detected_keywords": list(detected_keywords)}

        # Проверяем на намерение генерации изображений
        logger.info(f"Анализ текста для определения намерения: '{text}'")

        # При обнаружении намерения генерации изображений
        if any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in self.image_generation_keywords):
            matched_patterns = []
            for pattern in self.image_generation_keywords:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched = re.search(pattern, text_lower, re.IGNORECASE)
                    matched_patterns.append(matched.group(0))

            logger.info(f"🎨 Обнаружено намерение генерации изображения. Ключевые слова: {matched_patterns}")
            image_prompt = self._extract_image_prompt(text_lower, matched_patterns[0])
            logger.info(f"🎨 Извлеченный промпт для изображения: '{image_prompt}'")

            return IntentType.IMAGE_GENERATION, {"prompt": image_prompt or text, "detected_keywords": matched_patterns}

        # Учитываем контекст предыдущих сообщений, если он предоставлен
        if user_id and chat_context and user_id in self.context:
            previous_intent = self.context.get(user_id, {}).get('last_intent')
            if previous_intent:
                # Если в предыдущем сообщении было определено намерение и новое сообщение 
                # короткое или похоже на продолжение диалога, сохраняем предыдущее намерение
                if len(text_lower.split()) <= 5 or text_lower.startswith(('да', 'нет', 'конечно', 'yes', 'no', 'sure')):
                    logger.info(f"Continuing previous intent: {previous_intent}")
                    if previous_intent == IntentType.WEB_SEARCH:
                        return IntentType.WEB_SEARCH, {"query": text, "context_continuation": True}
                    elif previous_intent == IntentType.IMAGE_GENERATION:
                        return IntentType.IMAGE_GENERATION, {"prompt": text, "context_continuation": True}

        # Если не определено специфическое намерение, считаем что это обычный чат
        logger.info("No specific intent detected, defaulting to chat")
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

    def update_user_context(self, user_id: str, intent_type: IntentType, intent_data: Dict[str, Any]) -> None:
        """
        Обновление контекста пользователя для последующего анализа.

        Args:
            user_id: ID пользователя
            intent_type: Тип намерения
            intent_data: Данные намерения
        """
        if not user_id:
            return

        if user_id not in self.context:
            self.context[user_id] = {}

        self.context[user_id]['last_intent'] = intent_type
        self.context[user_id]['last_data'] = intent_data

        # Ограничиваем размер контекста
        if len(self.context) > 1000:
            # Удаляем старые записи
            oldest_keys = list(self.context.keys())[:100]
            for key in oldest_keys:
                del self.context[key]