# src/domain/entity/user.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import IntEnum


class UserState(IntEnum):
    """Состояния пользователя для пошаговых диалогов"""
    NONE = 0
    WAIT_EMAIL = 1
    WAIT_SYSTEM_PROMPT = 2
    WAIT_CHAT_NAME = 3
    WAIT_REFERRAL_CODE = 4


@dataclass
class User:
    """Сущность пользователя (аналог PHP Entity/User.php)"""
    id: Optional[int] = None
    tg_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    language_code: Optional[str] = "en"

    # BotHub интеграция
    bothub_id: Optional[str] = None
    bothub_group_id: Optional[str] = None
    bothub_access_token: Optional[str] = None
    bothub_access_token_created_at: Optional[datetime] = None

    # Состояние пользователя для диалогов
    state: Optional[int] = None

    # Настройки моделей и инструментов
    gpt_model: Optional[str] = None
    image_generation_model: Optional[str] = None
    tool: Optional[str] = None

    # Дополнительные данные
    present_data: Optional[str] = None
    current_chat_index: int = 1
    system_messages_to_delete: Optional[List[int]] = field(default_factory=list)
    referral_code: Optional[str] = None
    current_chat_list_page: int = 1

    # Служебные поля
    registered_at: Optional[datetime] = None

    def __post_init__(self):
        if self.system_messages_to_delete is None:
            self.system_messages_to_delete = []
        if self.registered_at is None:
            self.registered_at = datetime.now()

    def get_display_name(self) -> str:
        """Получить отображаемое имя пользователя"""
        if self.first_name:
            return f"{self.first_name} {self.last_name or ''}".strip()
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.tg_id}"

    def get_state(self) -> UserState:
        """Получить текущее состояние пользователя"""
        return UserState(self.state) if self.state is not None else UserState.NONE

    def set_state(self, state: UserState) -> None:
        """Установить состояние пользователя"""
        self.state = state.value if state else None

    def add_system_message_to_delete(self, message_id: int) -> None:
        """Добавить ID сообщения для удаления"""
        if self.system_messages_to_delete is None:
            self.system_messages_to_delete = []
        self.system_messages_to_delete.append(message_id)

    def clear_system_messages_to_delete(self) -> List[int]:
        """Получить и очистить список сообщений для удаления"""
        messages = self.system_messages_to_delete or []
        self.system_messages_to_delete = []
        return messages

    def is_token_valid(self, lifetime_seconds: int = 86390) -> bool:
        """Проверить, действителен ли токен доступа"""
        if not self.bothub_access_token or not self.bothub_access_token_created_at:
            return False

        time_diff = datetime.now() - self.bothub_access_token_created_at
        return time_diff.total_seconds() < lifetime_seconds