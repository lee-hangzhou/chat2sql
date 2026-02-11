import time
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, IntentParseResult
from app.vars.prompts import IR_AST_TAG, PERFORMANCE_FEEDBACK_TAG
from app.vars.vars import HUMAN_TYPE


class IntentParse:
    def __init__(self):
        self.structured_llm = llm.with_structured_output(IntentParseResult).with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )

    @staticmethod
    def _get_existing_ir_ast(state: NL2SQLState) -> str | None:
        if state.intent_parse_result and state.intent_parse_result.ir_ast:
            return state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        return None

    @staticmethod
    def _get_performance_feedback(state: NL2SQLState) -> str | None:
        if state.performance_result and not state.performance_result.is_ok:
            return "; ".join(state.performance_result.issues)
        return None

    @staticmethod
    def _trim_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
        """保留首条用户消息 + 最近 N 轮，防止 prompt 无限膨胀。

        ir_ast 已承载历史意图的结构化摘要，中间轮次的消息对 LLM 决策价值较低。
        """
        max_count = settings.AGENT_MAX_MESSAGE_PAIRS * 2 + 1
        if len(messages) <= max_count:
            return messages
        # 首条消息（原始意图）+ 最近 N 轮
        return [messages[0]] + messages[-(max_count - 1):]

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        if state.is_success is False:
            return {}

        logger.info("intent_parse.start")

        existing_ir_ast = self._get_existing_ir_ast(state)
        performance_feedback = self._get_performance_feedback(state)
        trimmed_messages = self._trim_messages(state.messages)
        schemas = "\n\n".join(state.schemas)

        params: Dict[str, Any] = {
            "messages": trimmed_messages,
            "schemas": schemas,
            "ir_ast_tag": "",
            "existing_ir_ast": "",
            "performance_feedback_tag": "",
            "performance_feedback": "",
        }
        if existing_ir_ast:
            params["ir_ast_tag"] = IR_AST_TAG
            params["existing_ir_ast"] = existing_ir_ast
        if performance_feedback:
            params["performance_feedback_tag"] = PERFORMANCE_FEEDBACK_TAG
            params["performance_feedback"] = performance_feedback
        prompt_messages = ChatPrompt.intent_recognition_prompt(**params)

        try:
            start = time.monotonic()
            result: IntentParseResult = await self.structured_llm.ainvoke(prompt_messages)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(
                "intent_parse.llm_completed",
                elapsed_ms=round(elapsed_ms, 1),
                need_follow_up=result.need_follow_up,
                need_retry_retrieve=result.need_retry_retrieve,
            )
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
