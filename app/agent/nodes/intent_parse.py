from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, IntentParseResult
from app.utils.messages import trim_messages
from app.utils.timing import log_elapsed


class IntentParse:
    """判断用户意图是否明确、schema 是否充足"""

    def __init__(self):
        self.structured_llm = llm.with_structured_output(IntentParseResult).with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        if state.is_success is False:
            return {}

        logger.info("intent_parse.start")

        trimmed_messages = trim_messages(state.messages)
        schemas = "\n\n".join(state.schemas)

        prompt_messages = ChatPrompt.intent_recognition_prompt(
            messages=trimmed_messages,
            schemas=schemas,
        )

        try:
            async with log_elapsed(logger, "intent_parse.llm_completed") as ctx:
                result: IntentParseResult = await self.structured_llm.ainvoke(prompt_messages)
                ctx["need_follow_up"] = result.need_follow_up
                ctx["need_retry_retrieve"] = result.need_retry_retrieve
        except Exception as e:
            logger.error("intent_parse.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": str(e),
            }

        return_dict: Dict[str, Any] = {"intent_parse_result": result}
        if result.need_follow_up and result.follow_up_question:
            return_dict["messages"] = [AIMessage(content=result.follow_up_question)]

        return return_dict
