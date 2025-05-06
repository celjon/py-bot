from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Present:
    """Сущность подарка токенов"""
    id: int
    user_id: int
    tokens: int
    notified: bool
    parsed_at: datetime
    notified_at: Optional[datetime] = None