import json
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agent.states import InsightState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode
from app.utils.timing import log_elapsed


class _AnalysisPlan(BaseModel):
    dimensions: List[str] = Field(default_factory=list, description="分析维度列表，3-5 个方向")


class InsightPlanner:
    """分析数据集结构，用 LLM 生成 3-5 个分析维度"""

    def __init__(self):
        self.structured_llm = (
            llm.with_structured_output(_AnalysisPlan)
            .with_retry(
                stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                wait_exponential_jitter=True,
            )
        )

    @staticmethod
    def _build_columns_summary(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "(无数据)"
        parts = []
        for col, val in rows[0].items():
            type_name = type(val).__name__ if val is not None else "unknown"
            parts.append(f"{col} ({type_name})")
        return ", ".join(parts)

    @staticmethod
    def _build_sample(rows: List[Dict[str, Any]], n: int = 3) -> str:
        if not rows:
            return "(empty)"
        return json.dumps(rows[:n], ensure_ascii=False, default=str)

    async def __call__(self, state: InsightState) -> Dict[str, Any]:
        rows = state.query_output
        question = state.user_question

        logger.info("insight_planner.start", row_count=len(rows), question=question)

        if not rows:
            logger.warning("insight_planner.empty_data")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": "数据集为空，无法制定分析计划",
            }

        columns_summary = self._build_columns_summary(rows)
        sample = self._build_sample(rows)

        system_prompt = (
            "你是一位数据分析专家。根据用户提问和数据集结构，制定 3 到 5 个有价值的分析维度，"
            "帮助从多角度深入理解数据。\n"
            "要求：\n"
            "- 每个维度是一个简短的中文短语（10字以内）\n"
            "- 维度应覆盖趋势、分布、对比、异常、相关性等角度\n"
            "- 输出 JSON，字段名 dimensions，值为字符串数组"
        )
        human_prompt = (
            "用户问题：{question}\n\n"
            "数据列信息：{columns_summary}\n\n"
            "数据样例（前 {sample_count} 行）：\n{sample}"
        )

        messages = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ]).format_messages(
            question=question,
            columns_summary=columns_summary,
            sample_count=min(3, len(rows)),
            sample=sample,
        )

        try:
            async with log_elapsed(logger, "insight_planner.llm_completed"):
                result: _AnalysisPlan = await self.structured_llm.ainvoke(messages)
        except Exception as e:
            logger.error("insight_planner.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        plan = result.dimensions or []
        logger.info("insight_planner.completed", plan_count=len(plan), plan=plan)
        return {"analysis_plan": plan}
