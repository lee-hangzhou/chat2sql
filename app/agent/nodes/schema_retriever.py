import asyncio
from typing import Any, Dict

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.logger import logger
from app.core.vector_store import vector_store_manager
from app.schemas.agent import AgentErrorCode
from app.utils.timing import log_elapsed
from app.vars.vars import HUMAN_TYPE


class SchemaRetriever:
    def __init__(self):
        self._vs_manager = vector_store_manager

    @staticmethod
    def _build_retrieval_query(state: NL2SQLState) -> str:
        """从对话历史中提取用户消息构建检索查询"""
        if not state.messages:
            return ""

        user_messages = [
            msg.content for msg in state.messages
            if msg.type == HUMAN_TYPE
        ]
        return "\n".join(user_messages)

    def _search(self, query: str) -> list[str]:
        results = self._vs_manager.vector_store.similarity_search(
            query, k=settings.MILVUS_SEARCH_LIMIT
        )
        return [doc.page_content for doc in results]

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        logger.info(
            "schema_retriever.start",
            schema_retry_count=state.schema_retry_count,
        )

        if state.schema_retry_count >= settings.AGENT_MAX_SCHEMA_RETRIES:
            logger.warning("schema_retriever.retry_limit_reached")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.SCHEMA_RETRY_LIMIT,
                "error_message": AgentErrorCode.SCHEMA_RETRY_LIMIT.message,
            }

        query = self._build_retrieval_query(state)
        if not query:
            logger.warning("schema_retriever.empty_query")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.EMPTY_QUERY,
                "error_message": AgentErrorCode.EMPTY_QUERY.message,
            }

        try:
            async with log_elapsed(logger, "schema_retriever.search_completed"):
                schemas = await asyncio.to_thread(self._search, query)
        except Exception as e:
            logger.error("schema_retriever.search_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.RETRIEVAL_ERROR,
                "error_message": str(e),
            }

        if not schemas:
            logger.warning("schema_retriever.no_results")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SCHEMA_RESULTS,
                "error_message": AgentErrorCode.NO_SCHEMA_RESULTS.message,
            }

        logger.info("schema_retriever.completed", schema_count=len(schemas))
        return {
            "schemas": schemas,
            "schema_retry_count": state.schema_retry_count + 1,
        }
