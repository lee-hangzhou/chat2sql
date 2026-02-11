from tortoise import fields

from app.models.base import BaseModel
from app.schemas.chat import ConversationStatus


class Conversation(BaseModel):
    user_id = fields.BigIntField(index=True)
    title = fields.CharField(max_length=200, default="")
    thread_id = fields.CharField(max_length=36, unique=True, index=True)
    status = fields.CharEnumField(
        ConversationStatus, default=ConversationStatus.ACTIVE, max_length=20
    )

    class Meta(BaseModel.Meta):
        table = "conversations"
        abstract = False
