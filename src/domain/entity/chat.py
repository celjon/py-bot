from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Chat:
    """Сущность чата"""
    id: int
    user_id: int
    chat_index: int

    # BotHub данные
    bothub_chat_id: Optional[str] = None
    bothub_chat_model: Optional[str] = None

    # Настройки чата
    context_remember: bool = True
    context_counter: int = 0
    links_parse: bool = False
    formula_to_image: bool = False
    answer_to_voice: bool = False

    # Данные
    name: Optional[str] = None
    system_prompt: str = ""
    buffer: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.buffer:
            self.buffer = {}

    def increment_context_counter(self) -> None:
        """Увеличивает счетчик контекста"""
        if self.context_remember:
            self.context_counter += 1

    def reset_context_counter(self) -> None:
        """Сбрасывает счетчик контекста"""
        self.context_counter = 0

    def add_to_buffer(self, text: Optional[str] = None,
                      file_name: Optional[str] = None,
                      display_file_name: Optional[str] = None) -> None:
        """Добавляет данные в буфер сообщений"""
        buffer_message = {}
        if text:
            buffer_message['text'] = text
        if file_name:
            buffer_message['fileName'] = file_name
        if display_file_name:
            buffer_message['displayFileName'] = display_file_name

        if buffer_message:
            if 'messages' not in self.buffer:
                self.buffer['messages'] = []
            self.buffer['messages'].append(buffer_message)

    def refresh_buffer(self) -> None:
        """Очищает буфер сообщений"""
        self.buffer = {}