from src.domain.entity.user import User
from typing import Optional

class MockUserRepository:
    async def find_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        return User(
            id=1,
            telegram_id=telegram_id,
            first_name="Test",
            last_name=None,
            username=None,
            language_code="en"
        )

    async def save(self, user: User) -> int:
        return 1

    async def update(self, user: User) -> None:
        pass