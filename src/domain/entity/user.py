from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    """Сущность пользователя"""
    id: int
    telegram_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    bothub_id: Optional[str] = None
    bothub_access_token: Optional[str] = None
    registered_at: datetime = datetime.now()
    current_chat_index: int = 1