import asyncio
from typing import Any, Dict, List

from langchain_core.messages import BaseMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, SQLResult
from app.utils.messages import trim_messages
from app.utils.timing import log_elapsed
from app.vars.prompts import VALIDATION_FEEDBACK_SECTION


class SQLGenerator:
    """基于对话历史和 schema 并发生成多条候选 SQL"""

    @staticmethod
    def _build_validation_feedback(state: NL2SQLState) -> str:
        """拼接上一轮校验反馈（语法/EXPLAIN/性能错误），无反馈返回空字符串"""
        feedback_parts: list[str] = []
        if state.syntax_result and not state.syntax_result.is_ok:
            feedback_parts.append(state.syntax_result.error)
        if state.explain_error:
            feedback_parts.append(state.explain_error)
        if state.performance_result and not state.performance_result.is_ok:
            feedback_parts.extend(state.performance_result.issues)

        if not feedback_parts:
            return ""

        previous_sql = ""
        if state.sql_candidates:
            previous_sql = state.sql_candidates[0].sql

        return VALIDATION_FEEDBACK_SECTION.format(
            previous_sql=previous_sql,
            validation_feedback="\n".join(feedback_parts),
        )

    @staticmethod
    def _build_prompt(state: NL2SQLState) -> List[BaseMessage]:
        """组装完整的 SQL 生成 prompt：schema + 对话历史 + 校验反馈"""
        schemas = "\n\n".join(state.schemas)
        trimmed = trim_messages(state.messages)
        feedback = SQLGenerator._build_validation_feedback(state)
        return ChatPrompt.generate_sql_prompt(
            messages=trimmed,
            schemas=schemas,
            validation_feedback_section=feedback,
        )

    @staticmethod
    async def _generate_single(prompt_messages: List[BaseMessage], temperature: float) -> SQLResult | None:
        """调用 LLM 生成单条 SQL，含指数退避重试，失败返回 None"""
        try:
            chain = (
                llm
                .bind(temperature=temperature)
                .with_structured_output(SQLResult)
                .with_retry(
                    stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                    wait_exponential_jitter=True,
                )
            )
            return await chain.ainvoke(prompt_messages)
        except Exception as e:
            logger.warning("sql_generator.candidate_failed", error=str(e))
            return None

    async def _generate_candidates(
        self, prompt_messages: List[BaseMessage], count: int, temperature: float,
    ) -> List[SQLResult]:
        """并发生成指定数量的候选 SQL，过滤空结果"""
        async with log_elapsed(logger, "sql_generator.candidates_completed") as ctx:
            tasks = [self._generate_single(prompt_messages, temperature) for _ in range(count)]
            results = await asyncio.gather(*tasks)
            candidates = [r for r in results if r is not None and r.sql]
            ctx["total"] = count
            ctx["valid"] = len(candidates)
        return candidates

    @staticmethod
    def _build_result(candidates: List[SQLResult], is_arbitration: bool) -> Dict[str, Any]:
        """构建生成结果，非仲裁模式时重置选优相关状态"""
        result: Dict[str, Any] = {
            "sql_candidates": candidates,
            "sql_result": None,
            "syntax_result": None,
            "explain_error": None,
            "performance_result": None,
            "needs_arbitration": False,
        }
        if not is_arbitration:
            result["candidate_exec_results"] = []
            result["validated_candidates"] = []
        return result

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        """编排 SQL 生成流程：构建 prompt → 并发生成候选 → 组装输出"""
        is_arbitration = state.needs_arbitration
        candidate_count = 1 if is_arbitration else settings.SQL_CANDIDATE_COUNT

        logger.info(
            "sql_generator.start",
            retry_count=state.retry_count,
            candidate_count=candidate_count,
            arbitration=is_arbitration,
        )

        prompt_messages = self._build_prompt(state)
        candidates = await self._generate_candidates(
            prompt_messages, candidate_count, settings.SQL_CANDIDATE_TEMPERATURE,
        )

        if not candidates:
            logger.error("sql_generator.all_candidates_failed")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        return self._build_result(candidates, is_arbitration)
