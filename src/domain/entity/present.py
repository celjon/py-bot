from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Present:
    """Сущность подарка токенов (аналог PHP Entity/Present.php)"""
    id: Optional[int] = None
    user_id: int = 0
    tokens: int = 0
    notified: bool = False
    parsed_at: Optional[datetime] = None
    notified_at: Optional[datetime] = None

    def __post_init__(self):
        if self.parsed_at is None:
            self.parsed_at = datetime.now()

    def mark_notified(self) -> None:
        """Отметить подарок как уведомленный"""
        self.notified = True
        self.notified_at = datetime.now()

    def get_tokens_display(self) -> str:
        """Получить отображение количества токенов"""
        if self.tokens >= 1000000:
            return f"{self.tokens // 1000000}M tokens"
        elif self.tokens >= 1000:
            return f"{self.tokens // 1000}K tokens"
        else:
            return f"{self.tokens} tokens"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tokens': self.tokens,
            'notified': self.notified,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None,
            'notified_at': self.notified_at.isoformat() if self.notified_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Present':
        """Создание объекта из словаря"""
        present = cls(
            id=data.get('id'),
            user_id=data.get('user_id', 0),
            tokens=data.get('tokens', 0),
            notified=data.get('notified', False)
        )

        # Парсим даты
        if data.get('parsed_at'):
            present.parsed_at = datetime.fromisoformat(data['parsed_at'].replace('Z', '+00:00'))
        if data.get('notified_at'):
            present.notified_at = datetime.fromisoformat(data['notified_at'].replace('Z', '+00:00'))

        return present