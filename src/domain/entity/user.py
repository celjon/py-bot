
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class User:
    """Сущность пользователя"""
    id: int
    telegram_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None  # Добавляем поле email
    language_code: Optional[str] = "en"

    # BotHub данные
    bothub_id: Optional[str] = None
    bothub_group_id: Optional[str] = None
    bothub_access_token: Optional[str] = None
    bothub_access_token_created_at: Optional[datetime] = None

    # Данные по чатам
    current_chat_index: int = 1
    current_chat_list_page: int = 1

    # Модели по умолчанию
    gpt_model: Optional[str] = None
    image_generation_model: Optional[str] = None

    # Настройки
    formula_to_image: bool = False
    links_parse: bool = False
    context_remember: bool = True
    answer_to_voice: bool = False

    # Состояние пользователя (для диалогов)
    state: Optional[str] = None

    # Дополнительные данные
    present_data: Optional[str] = None
    referral_code: Optional[str] = None
    buffer: Optional[Dict[str, Any]] = field(default_factory=dict)
    system_messages_to_delete: Optional[List[int]] = field(default_factory=list)

    def __post_init__(self):
        if not self.buffer:
            self.buffer = {}
        if not self.system_messages_to_delete:
            self.system_messages_to_delete = []