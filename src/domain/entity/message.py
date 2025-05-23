from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import IntEnum
import json


class MessageDirection(IntEnum):
    """Направление сообщения"""
    REQUEST = 0  # Входящее сообщение от пользователя
    RESPONSE = 1  # Исходящее сообщение к пользователю


class MessageType(IntEnum):
    """Типы сообщений"""
    NO_ACTION = 0
    START = 1
    SEND_MESSAGE = 2
    GET_USER_INFO = 3
    CREATE_NEW_CHAT = 4
    RESET_CONTEXT = 5
    SAVE_SYSTEM_PROMPT = 6
    CHANGE_MODEL = 7
    ENABLE_WEB_SEARCH = 8
    VOICE_MESSAGE = 9
    IMAGE_MESSAGE = 10
    DOCUMENT_MESSAGE = 11


class MessageStatus(IntEnum):
    """Статусы обработки сообщений"""
    NOT_PROCESSED = 0
    PROCESSED = 1
    PROCESSING = 2
    ERROR = 3


@dataclass
class Message:
    """Сущность сообщения (аналог PHP Entity/Message.php)"""
    id: Optional[int] = None
    user_id: int = 0
    chat_index: int = 1
    message_id: int = 0
    direction: MessageDirection = MessageDirection.REQUEST
    type: MessageType = MessageType.NO_ACTION
    status: MessageStatus = MessageStatus.NOT_PROCESSED
    chat_id: int = 0
    text: str = ""
    data: Optional[Dict[str, Any]] = field(default_factory=dict)
    sent_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    worker: Optional[int] = None
    related_message_id: Optional[int] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.sent_at is None:
            self.sent_at = datetime.now()
        if self.parsed_at is None:
            self.parsed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'chat_index': self.chat_index,
            'message_id': self.message_id,
            'direction': self.direction.value,
            'type': self.type.value,
            'status': self.status.value,
            'chat_id': self.chat_id,
            'text': self.text,
            'data': self.data,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'worker': self.worker,
            'related_message_id': self.related_message_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Создание объекта из словаря"""
        message = cls()
        message.id = data.get('id')
        message.user_id = data.get('user_id', 0)
        message.chat_index = data.get('chat_index', 1)
        message.message_id = data.get('message_id', 0)
        message.direction = MessageDirection(data.get('direction', 0))
        message.type = MessageType(data.get('type', 0))
        message.status = MessageStatus(data.get('status', 0))
        message.chat_id = data.get('chat_id', 0)
        message.text = data.get('text', '')
        message.data = data.get('data', {})

        # Парсим даты
        if data.get('sent_at'):
            message.sent_at = datetime.fromisoformat(data['sent_at'].replace('Z', '+00:00'))
        if data.get('parsed_at'):
            message.parsed_at = datetime.fromisoformat(data['parsed_at'].replace('Z', '+00:00'))

        message.worker = data.get('worker')
        message.related_message_id = data.get('related_message_id')

        return message

    def set_data(self, key: str, value: Any) -> None:
        """Установить значение в поле data"""
        if self.data is None:
            self.data = {}
        self.data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        """Получить значение из поля data"""
        return self.data.get(key, default) if self.data else default

    def is_request(self) -> bool:
        """Проверить, является ли сообщение запросом"""
        return self.direction == MessageDirection.REQUEST

    def is_response(self) -> bool:
        """Проверить, является ли сообщение ответом"""
        return self.direction == MessageDirection.RESPONSE

    def mark_processed(self) -> None:
        """Отметить сообщение как обработанное"""
        self.status = MessageStatus.PROCESSED
        self.parsed_at = datetime.now()

    def mark_processing(self, worker_id: int) -> None:
        """Отметить сообщение как обрабатываемое"""
        self.status = MessageStatus.PROCESSING
        self.worker = worker_id

    def mark_error(self) -> None:
        """Отметить сообщение как ошибочное"""
        self.status = MessageStatus.ERROR