from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.base import PaginatedResponse, Response
from app.schemas.chat import (
    ConversationDeleteRequest,
    ConversationDetailRequest,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationListRequest,
    SchemaSyncResponse,
    SendMessageRequest,
)
from app.services import registry

router = APIRouter()


@router.post("/conversations/create")
async def create_conversation(request: Request) -> Response[ConversationListItem]:
    user_id = int(request.state.user_id)
    result = await registry.chat_service.create_conversation(user_id)
    return Response(data=result)


@router.post("/conversations/list")
async def list_conversations(
    request: Request, body: ConversationListRequest
) -> Response[PaginatedResponse[ConversationListItem]]:
    user_id = int(request.state.user_id)
    items, total = await registry.chat_service.list_conversations(
        user_id, body.offset, body.limit
    )
    return Response(data=PaginatedResponse(items=items, total=total))


@router.post("/conversations/detail")
async def get_conversation_detail(
    request: Request, body: ConversationDetailRequest
) -> Response[ConversationDetailResponse]:
    graph = request.app.state.nl2sql_graph
    user_id = int(request.state.user_id)
    result = await registry.chat_service.get_conversation_detail(
        graph, body.conversation_id, user_id
    )
    return Response(data=result)


@router.post("/conversations/delete")
async def delete_conversation(
    request: Request, body: ConversationDeleteRequest
) -> Response[None]:
    user_id = int(request.state.user_id)
    await registry.chat_service.delete_conversation(body.conversation_id, user_id)
    return Response(data=None)


@router.post("/conversations/messages/send")
async def send_message(request: Request, body: SendMessageRequest):
    """发送消息并以 SSE 事件流返回 graph 执行进度与结果"""
    graph = request.app.state.nl2sql_graph
    user_id = int(request.state.user_id)
    stream = await registry.chat_service.send_message_stream(
        graph, body.conversation_id, user_id, body.content
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/schema/sync")
async def sync_schema() -> Response[SchemaSyncResponse]:
    """从业务数据库全量同步表结构到 Milvus"""
    table_count = await registry.schema_service.sync()
    return Response(data=SchemaSyncResponse(table_count=table_count))
