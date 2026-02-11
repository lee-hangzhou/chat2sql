import time
from typing import Any, Dict

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, SQLResult
from app.vars.prompts import VALIDATION_FEEDBACK_TAG


class SQLGenerator:
    def __init__(self):
        self.structured_llm = llm.with_structured_output(SQLResult).with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )

    @staticmethod
    def _get_validation_feedback(state: NL2SQLState) -> str | None:
        """从校验结果中提取失败原因，用于指导 SQL 重新生成"""
        if state.syntax_result and not state.syntax_result.is_ok:
            return state.syntax_result.error
        if state.explain_error:
            return state.explain_error
        return None

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        logger.info("sql_generator.start", retry_count=state.retry_count)

        if not state.intent_parse_result or not state.intent_parse_result.ir_ast:
            logger.warning("sql_generator.no_ir_ast")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_IR_AST,
                "error_message": AgentErrorCode.NO_IR_AST.message,
            }

        ir_ast = state.intent_parse_result.ir_ast.model_dump_json(indent=2)
        schemas = "\n\n".join(state.schemas)
        validation_feedback = self._get_validation_feedback(state)

        params: Dict[str, Any] = {
            "schemas": schemas,
            "ir_ast": ir_ast,
            "validation_feedback_tag": "",
            "validation_feedback": "",
        }
        if validation_feedback:
            params["validation_feedback_tag"] = VALIDATION_FEEDBACK_TAG
            params["validation_feedback"] = validation_feedback

        prompt_message = ChatPrompt.generate_prompt(**params)

        try:
            start = time.monotonic()
            result: SQLResult = await self.structured_llm.ainvoke(prompt_message)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info("sql_generator.llm_completed", elapsed_ms=round(elapsed_ms, 1))
        except Exception as e:
            logger.error("sql_generator.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": str(e),
            }

        # 清除上一轮校验结果，防止 state 残留影响下一轮
        return {
            "sql_result": result,
            "syntax_result": None,
            "explain_error": None,
            "performance_result": None,
        }
