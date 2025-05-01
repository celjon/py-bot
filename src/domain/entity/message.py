from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class MessageDirection(Enum):
    REQUEST = 0
    RESPONSE = 1

class MessageType(Enum):
    NO_ACTION = 0
    START = 1
    SEND_MESSAGE = 2
    GET_USER_INFO = 3
    CREATE_NEW_CHAT = 4
    # Добавьте другие типы по мере необходимости

class MessageStatus(Enum):
    NOT_PROCESSED = 0
    PROCESSED = 1

class Message(BaseModel):
    """Сущность сообщения"""
    id: Optional[int] = None
    user_id: int
    message_id: int
    chat_id: int
    chat_index: int = 1
    direction: MessageDirection
    type: MessageType
    status: MessageStatus = MessageStatus.NOT_PROCESSED
    text: str
    data: Optional[Dict[str, Any]] = None
    worker: Optional[int] = None
    sent_at: datetime = datetime.now()
    parsed_at: datetime = datetime.now()