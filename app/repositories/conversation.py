from typing import List, Optional, Tuple

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository
from app.schemas.chat import ConversationStatus


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self) -> None:
        self.model = Conversation

    async def get_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Conversation], int]:
        query = self.model.filter(user_id=user_id)
        total = await query.count()
        items = await query.order_by("-updated_at").offset(offset).limit(limit)
        return items, total

    async def get_by_id_and_user(
        self,
        conversation_id: int,
        user_id: int,
    ) -> Optional[Conversation]:
        return await self.model.filter(id=conversation_id, user_id=user_id).first()

    async def update_status(
        self,
        conversation_id: int,
        status: ConversationStatus,
    ) -> None:
        await self.model.filter(id=conversation_id).update(status=status)

    async def update_title(
        self,
        conversation_id: int,
        title: str,
    ) -> None:
        await self.model.filter(id=conversation_id).update(title=title)
