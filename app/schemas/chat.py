from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversationStatus(str, Enum):
    """对话状态"""

    ACTIVE = "active"
    WAITING_FOLLOW_UP = "waiting_follow_up"
    COMPLETED = "completed"
    FAILED = "failed"


# --------------- Request ---------------


class ConversationListRequest(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ConversationDetailRequest(BaseModel):
    conversation_id: int


class ConversationDeleteRequest(BaseModel):
    conversation_id: int


class SendMessageRequest(BaseModel):
    conversation_id: int
    content: str = Field(..., min_length=1, max_length=2000)


# --------------- Response ---------------


class ConversationListItem(BaseModel):
    id: int
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageItem(BaseModel):
    role: str = Field(..., description="user 或 assistant")
    content: str


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    messages: List[MessageItem] = Field(default_factory=list)

    sql: Optional[str] = None
    execute_result: Optional[List[Dict[str, Any]]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    follow_up_question: Optional[str] = None
