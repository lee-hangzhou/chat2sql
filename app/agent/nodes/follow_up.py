from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode


class FollowUp:
    def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        logger.info("follow_up.start", follow_up_count=state.follow_up_count)

        if state.follow_up_count >= settings.AGENT_MAX_FOLLOW_UPS:
            logger.warning("follow_up.limit_reached")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.FOLLOW_UP_LIMIT,
                "error_message": AgentErrorCode.FOLLOW_UP_LIMIT.message,
            }

        user_reply = interrupt(state.intent_parse_result.follow_up_question)
        logger.info("follow_up.user_replied")
        return {
            "messages": [HumanMessage(content=user_reply)],
            "follow_up_count": state.follow_up_count + 1,
            "schema_retry_count": 0,
        }
