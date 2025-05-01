from src.domain.entity.chat import Chat
from typing import Optional

class MockChatRepository:
    async def find_by_user_id_and_chat_index(self, user_id: int, chat_index: int) -> Optional[Chat]:
        return Chat(
            id=1,
            user_id=user_id,
            chat_index=chat_index,
            context_counter=0
        )

    async def save(self, chat: Chat) -> int:
        return 1

    async def update(self, chat: Chat) -> None:
        pass