import json
import uuid
from typing import Any, AsyncGenerator, Dict

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import settings
from app.core.logger import logger
from app.vars.vars import HUMAN_TYPE, ROLE_ASSISTANT, ROLE_USER
from app.exceptions.base import ConversationAccessDeniedError, ConversationNotFoundError
from app.models.conversation import Conversation
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import (
    ConversationDetailResponse,
    ConversationListItem,
    ConversationStatus,
    MessageItem,
)


class ChatService:
    def __init__(self) -> None:
        self.repo = ConversationRepository()

    async def create_conversation(self, user_id: int) -> ConversationListItem:
        conversation = await self.repo.create(
            user_id=user_id,
            thread_id=str(uuid.uuid4()),
            status=ConversationStatus.ACTIVE,
        )
        return ConversationListItem.model_validate(conversation)

    async def list_conversations(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ConversationListItem], int]:
        items, total = await self.repo.get_by_user(user_id, offset, limit)
        return [ConversationListItem.model_validate(item) for item in items], total

    async def get_conversation_detail(
        self,
        graph: CompiledStateGraph,
        conversation_id: int,
        user_id: int,
    ) -> ConversationDetailResponse:
        conversation = await self._get_owned_conversation(conversation_id, user_id)
        config = self._build_config(conversation.thread_id)

        messages: list[MessageItem] = []
        sql = None
        execute_result = None
        error_code = None
        error_message = None
        follow_up_question = None

        state = await graph.aget_state(config)
        if state and state.values:
            values = state.values
            for msg in values.get("messages", []):
                role = ROLE_USER if msg.type == HUMAN_TYPE else ROLE_ASSISTANT
                messages.append(MessageItem(role=role, content=msg.content))

            sql_result = values.get("sql_result")
            if sql_result:
                sql = getattr(sql_result, "sql", None) or sql_result.get("sql")

            execute_result = self._stringify_rows(values.get("execute_result"))

            ec = values.get("error_code")
            error_code = ec.value if ec else None
            error_message = values.get("error_message")

            ipr = values.get("intent_parse_result")
            if conversation.status == ConversationStatus.WAITING_FOLLOW_UP and ipr:
                follow_up_question = (
                    getattr(ipr, "follow_up_question", None)
                    or ipr.get("follow_up_question")
                )

        return ConversationDetailResponse(
            id=conversation.id,
            title=conversation.title,
            status=ConversationStatus(conversation.status),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=messages,
            sql=sql,
            execute_result=execute_result,
            error_code=error_code,
            error_message=error_message,
            follow_up_question=follow_up_question,
        )

    async def delete_conversation(
        self,
        conversation_id: int,
        user_id: int,
    ) -> None:
        await self._get_owned_conversation(conversation_id, user_id)
        await self.repo.delete(conversation_id)

    async def send_message_stream(
        self,
        graph: CompiledStateGraph,
        conversation_id: int,
        user_id: int,
        content: str,
    ) -> AsyncGenerator[str, None]:
        """校验权限并构建输入，返回 SSE 事件流的异步生成器
        """
        conversation = await self._get_owned_conversation(conversation_id, user_id)
        config = self._build_config(conversation.thread_id)

        if not conversation.title:
            await self.repo.update_title(conversation.id, content[:100])

        if conversation.status == ConversationStatus.WAITING_FOLLOW_UP:
            input_data: Any = Command(resume=content)
        else:
            await self.repo.update_status(conversation.id, ConversationStatus.ACTIVE)
            input_data = {
                "messages": [HumanMessage(content=content)],
                "user_id": str(user_id),
                "retry_count": 0,
                "schema_retry_count": 0,
                "follow_up_count": 0,
                "is_success": None,
                "error_code": None,
                "error_message": None,
            }

        return self._stream_graph(graph, conversation, config, input_data)



    async def _stream_graph(
        self,
        graph: CompiledStateGraph,
        conversation: Conversation,
        config: dict,
        input_data: Any,
    ) -> AsyncGenerator[str, None]:
        """执行 graph 并以 SSE 事件流形式逐步返回节点执行进度与最终结果"""
        try:
            async for event in graph.astream(
                input_data, config, stream_mode="updates"
            ):
                for node_name in event:
                    yield self._sse_event("node_complete", {"node": node_name})

            # graph 执行结束，判断终态
            state = await graph.aget_state(config)
            if state.next:
                # graph 被 interrupt 挂起，等待用户追问回复
                await self.repo.update_status(
                    conversation.id, ConversationStatus.WAITING_FOLLOW_UP
                )
                ipr = state.values.get("intent_parse_result")
                question = ""
                if ipr:
                    question = (
                        getattr(ipr, "follow_up_question", None)
                        or ipr.get("follow_up_question", "")
                        or ""
                    )
                yield self._sse_event("follow_up", {"question": question})
            else:
                values = state.values
                if values.get("is_success"):
                    await self.repo.update_status(
                        conversation.id, ConversationStatus.COMPLETED
                    )
                    sql_result = values.get("sql_result")
                    sql = None
                    if sql_result:
                        sql = getattr(sql_result, "sql", None) or sql_result.get(
                            "sql"
                        )
                    yield self._sse_event(
                        "result",
                        {
                            "sql": sql,
                            "execute_result": self._stringify_rows(values.get("execute_result")),
                        },
                    )
                else:
                    await self.repo.update_status(
                        conversation.id, ConversationStatus.FAILED
                    )
                    ec = values.get("error_code")
                    yield self._sse_event(
                        "error",
                        {
                            "error_code": ec.value if ec else None,
                            "error_message": values.get("error_message"),
                        },
                    )

            yield self._sse_event("done", {})

        except Exception as e:
            logger.exception(
                "chat.stream_error",
                conversation_id=conversation.id,
                error=str(e),
            )
            await self.repo.update_status(
                conversation.id, ConversationStatus.FAILED
            )
            yield self._sse_event("error", {"error_message": str(e)})
            yield self._sse_event("done", {})

    async def _get_owned_conversation(
        self, conversation_id: int, user_id: int
    ) -> Conversation:
        """获取并校验对话归属权"""
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundError()
        if conversation.user_id != user_id:
            raise ConversationAccessDeniedError()
        return conversation

    @staticmethod
    def _build_config(thread_id: str) -> dict:
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.AGENT_RECURSION_LIMIT,
        }

    @staticmethod
    def _sse_event(event: str, data: Dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    @staticmethod
    def _stringify_rows(rows: list[dict] | None) -> list[dict] | None:
        if not rows:
            return rows
        return [
            {k: str(v) if isinstance(v, int) else v for k, v in row.items()}
            for row in rows
        ]
