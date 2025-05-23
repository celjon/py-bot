from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json


@dataclass
class Chat:
    """Сущность чата пользователя (аналог PHP Entity/UserChat.php)"""
    id: Optional[int] = None
    user_id: int = 0
    chat_index: int = 1
    bothub_chat_id: Optional[str] = None
    bothub_chat_model: Optional[str] = None
    context_remember: bool = True
    context_counter: int = 0
    links_parse: bool = False
    buffer: Optional[Dict[str, Any]] = field(default_factory=dict)
    system_prompt: str = ""
    formula_to_image: bool = False
    answer_to_voice: bool = False
    name: Optional[str] = None

    def __post_init__(self):
        if self.buffer is None:
            self.buffer = {}

    def increment_context_counter(self) -> None:
        """Увеличить счетчик контекста"""
        if self.context_remember:
            self.context_counter += 1

    def reset_context_counter(self) -> None:
        """Сбросить счетчик контекста"""
        self.context_counter = 0

    def add_to_buffer(self, text: Optional[str] = None,
                      file_name: Optional[str] = None,
                      display_file_name: Optional[str] = None) -> None:
        """Добавить данные в буфер сообщений"""
        if self.buffer is None:
            self.buffer = {}

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
        """Очистить буфер сообщений"""
        self.buffer = {}

    def get_display_name(self) -> str:
        """Получить отображаемое имя чата"""
        if self.name:
            return self.name

        # Стандартные названия для первых 5 чатов
        chat_names = {
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "📝"
        }

        return chat_names.get(self.chat_index, f"Chat {self.chat_index}")

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'chat_index': self.chat_index,
            'bothub_chat_id': self.bothub_chat_id,
            'bothub_chat_model': self.bothub_chat_model,
            'context_remember': self.context_remember,
            'context_counter': self.context_counter,
            'links_parse': self.links_parse,
            'buffer': self.buffer,
            'system_prompt': self.system_prompt,
            'formula_to_image': self.formula_to_image,
            'answer_to_voice': self.answer_to_voice,
            'name': self.name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserChat':
        """Создание объекта из словаря"""
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id', 0),
            chat_index=data.get('chat_index', 1),
            bothub_chat_id=data.get('bothub_chat_id'),
            bothub_chat_model=data.get('bothub_chat_model'),
            context_remember=data.get('context_remember', True),
            context_counter=data.get('context_counter', 0),
            links_parse=data.get('links_parse', False),
            buffer=data.get('buffer', {}),
            system_prompt=data.get('system_prompt', ''),
            formula_to_image=data.get('formula_to_image', False),
            answer_to_voice=data.get('answer_to_voice', False),
            name=data.get('name')
        )