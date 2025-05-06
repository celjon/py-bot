from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class ReferralTemplate:
    """Шаблон реферальной программы"""
    id: str
    name: str
    currency: str
    encourage_percentage: float
    min_withdraw_amount: int
    tokens: int
    locale: str = "ru"
    plan: Optional[Dict[str, Any]] = None
    disabled: bool = False
    private: bool = False


@dataclass
class ReferralProgram:
    """Реферальная программа"""
    id: str
    code: str
    owner_id: str
    participants: int
    balance: int
    template_id: str
    name: Optional[str] = None
    disabled: bool = False
    template: Optional[ReferralTemplate] = None
    amount_spend_by_users: int = 0
    last_withdrawed_at: Optional[datetime] = None