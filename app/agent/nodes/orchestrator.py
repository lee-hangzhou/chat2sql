from typing import Any, Dict

from app.agent.prompts import ChatPrompt
from app.agent.states import OrchestratorState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, OrchestratorIntent, OrchestratorIntentResult
from app.utils.timing import log_elapsed


class Orchestrator:
    """读取对话历史，通过 LLM 统一判断当前轮次意图"""

    def __init__(self):
        self.structured_llm = (
            llm.with_structured_output(OrchestratorIntentResult)
            .with_retry(
                stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                wait_exponential_jitter=True,
            )
        )

    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        prompt_messages = ChatPrompt.orchestrator_prompt(messages=state.messages)

        try:
            async with log_elapsed(logger, "orchestrator.llm_completed"):
                result: OrchestratorIntentResult = await self.structured_llm.ainvoke(prompt_messages)
        except Exception as e:
            logger.error("orchestrator.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        logger.info("orchestrator.completed", intent=result.intent.value)
        return {"current_intent": result.intent}
