from typing import Any, Dict

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, JudgeResult, SQLResult
from app.utils.timing import log_elapsed


class SQLJudge:
    """LLM 语义裁决：从结果不一致的候选中选择最正确的 SQL"""

    def __init__(self):
        self.structured_llm = llm.with_structured_output(JudgeResult).with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        """将所有候选 SQL 和上下文交给 LLM 裁决，返回语义最优的 SQL"""
        exec_results = state.candidate_exec_results
        if not exec_results:
            logger.warning("sql_judge.no_candidates")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        schemas = "\n\n".join(state.schemas)
        candidates_text = "\n".join(
            f"{i + 1}. {r.sql}" for i, r in enumerate(exec_results)
        )

        prompt_messages = ChatPrompt.judge_prompt(
            messages=state.messages,
            schemas=schemas,
            candidates_text=candidates_text,
        )

        try:
            async with log_elapsed(logger, "sql_judge.completed"):
                result: JudgeResult = await self.structured_llm.ainvoke(prompt_messages)
        except Exception as e:
            logger.error("sql_judge.failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": str(e),
            }

        idx = result.choice - 1
        if 0 <= idx < len(exec_results):
            logger.info("sql_judge.selected", index=idx)
            return {"sql_result": SQLResult(sql=exec_results[idx].sql)}

        logger.warning("sql_judge.invalid_choice", choice=result.choice)
        return {"sql_result": SQLResult(sql=exec_results[0].sql)}
