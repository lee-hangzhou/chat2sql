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


class _Anomaly(BaseModel):
    field: str = Field(description="异常发生的字段名")
    value: Any = Field(description="异常值")
    description: str = Field(description="异常性质及可能影响的中文描述")


class _AnomalyList(BaseModel):
    anomalies: List[_Anomaly] = Field(default_factory=list, description="检测到的异常点列表")


class AnomalyDetector:
    """按分析维度检测数据中的异常点，包括均值偏差、趋势突变、空值聚集等"""

    def __init__(self):
        self.structured_llm = (
            llm.with_structured_output(_AnomalyList)
            .with_retry(
                stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                wait_exponential_jitter=True,
            )
        )

    @staticmethod
    def _build_sample(rows: List[Dict[str, Any]], n: int = 10) -> str:
        if not rows:
            return "(empty)"
        return json.dumps(rows[:n], ensure_ascii=False, default=str)

    async def __call__(self, state: InsightState) -> Dict[str, Any]:
        rows = state.query_output
        plan = state.analysis_plan

        logger.info("anomaly_detector.start", row_count=len(rows), plan_count=len(plan))

        if not rows:
            logger.warning("anomaly_detector.empty_data")
            return {"anomalies": []}

        sample = self._build_sample(rows)
        plan_text = "\n".join(f"- {d}" for d in plan)

        system_prompt = (
            "你是一位数据质量和异常检测专家。根据提供的数据集和分析维度，"
            "识别数据中的异常点，包括：均值偏差过大、趋势突变、空值聚集、极端值等。\n"
            "输出 JSON，字段名 anomalies，每个元素包含：\n"
            "  - field: 异常字段名\n"
            "  - value: 异常值（字符串或数字）\n"
            "  - description: 中文描述该异常的性质和可能影响\n"
            "若未发现异常，返回空列表。"
        )
        human_prompt = (
            "分析维度：\n{plan}\n\n"
            "数据样例（前 {sample_count} 行）：\n{sample}\n\n"
            "总行数：{row_count}"
        )

        messages = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ]).format_messages(
            plan=plan_text,
            sample_count=min(10, len(rows)),
            sample=sample,
            row_count=len(rows),
        )

        try:
            async with log_elapsed(logger, "anomaly_detector.llm_completed"):
                result: _AnomalyList = await self.structured_llm.ainvoke(messages)
        except Exception as e:
            logger.error("anomaly_detector.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        anomalies = [a.model_dump() for a in result.anomalies]
        logger.info("anomaly_detector.completed", anomaly_count=len(anomalies))
        return {"anomalies": anomalies}
