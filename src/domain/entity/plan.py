from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Plan:
    """Сущность тарифного плана (аналог PHP Entity/Plan.php)"""
    id: Optional[int] = None
    bothub_id: Optional[str] = None
    type: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    tokens: Optional[int] = None

    def get_display_name(self) -> str:
        """Получить отображаемое имя плана"""
        if self.type:
            return self.type.replace('_', ' ').title()
        return f"Plan {self.id or 'Unknown'}"

    def get_formatted_price(self) -> str:
        """Получить отформатированную цену"""
        if self.price is not None and self.currency:
            return f"{self.price:.2f} {self.currency.upper()}"
        return "Free"

    def get_tokens_display(self) -> str:
        """Получить отображение количества токенов"""
        if self.tokens:
            if self.tokens >= 1000000:
                return f"{self.tokens // 1000000}M tokens"
            elif self.tokens >= 1000:
                return f"{self.tokens // 1000}K tokens"
            else:
                return f"{self.tokens} tokens"
        return "Unlimited"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'bothub_id': self.bothub_id,
            'type': self.type,
            'price': self.price,
            'currency': self.currency,
            'tokens': self.tokens
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """Создание объекта из словаря"""
        return cls(
            id=data.get('id'),
            bothub_id=data.get('bothub_id'),
            type=data.get('type'),
            price=data.get('price'),
            currency=data.get('currency'),
            tokens=data.get('tokens')
        )