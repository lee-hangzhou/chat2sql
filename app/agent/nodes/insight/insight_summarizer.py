import json
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agent.states import InsightFinding, InsightState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode
from app.utils.timing import log_elapsed


class _InsightReport(BaseModel):
    findings: List[InsightFinding] = Field(default_factory=list, description="结构化洞察结论列表")
    insight_summary: str = Field(default="", description="面向业务人员的整体洞察摘要")


class InsightSummarizer:
    """将验证假设和异常点整理为结构化 InsightFinding 列表，并生成总结报告"""

    def __init__(self):
        self.structured_llm = (
            llm.with_structured_output(_InsightReport)
            .with_retry(
                stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                wait_exponential_jitter=True,
            )
        )

    @staticmethod
    def _build_hypothesis_text(hypotheses: List[str]) -> str:
        if not hypotheses:
            return "(无验证假设)"
        return "\n".join(f"- {h}" for h in hypotheses)

    @staticmethod
    def _build_anomaly_text(anomalies: List[Dict[str, Any]]) -> str:
        if not anomalies:
            return "(无异常点)"
        return json.dumps(anomalies, ensure_ascii=False, default=str)

    async def __call__(self, state: InsightState) -> Dict[str, Any]:
        logger.info(
            "insight_summarizer.start",
            validated_hypotheses_count=len(state.validated_hypotheses),
            anomaly_count=len(state.anomalies),
        )

        hypothesis_text = self._build_hypothesis_text(state.validated_hypotheses)
        anomaly_text = self._build_anomaly_text(state.anomalies)

        system_prompt = (
            "你是一位商业智能分析师，擅长将数据分析结果整理为简洁有力的洞察报告。\n"
            "任务：\n"
            "1. 将验证通过的假设和异常点整理为结构化洞察结论列表（findings），每条包含：\n"
            "   - conclusion: 洞察结论，一句话总结\n"
            "   - data_slice: 支撑该结论的关键数据片段，dict 格式\n"
            "   - chart_suggestion: 建议展示的 ECharts 图表类型（bar/line/pie/scatter 等，无建议则为 null）\n"
            "   - severity: 重要程度，取值 high / medium / low\n"
            "2. 生成 insight_summary：面向业务人员的整体洞察摘要，200字以内\n"
            "输出 JSON，字段：findings（列表），insight_summary（字符串）。"
        )
        human_prompt = (
            "用户问题：{question}\n\n"
            "验证通过的假设：\n{hypothesis_text}\n\n"
            "检测到的异常点：\n{anomaly_text}"
        )

        messages = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ]).format_messages(
            question=state.user_question,
            hypothesis_text=hypothesis_text,
            anomaly_text=anomaly_text,
        )

        try:
            async with log_elapsed(logger, "insight_summarizer.llm_completed"):
                result: _InsightReport = await self.structured_llm.ainvoke(messages)
        except Exception as e:
            logger.error("insight_summarizer.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        logger.info(
            "insight_summarizer.completed",
            findings_count=len(result.findings),
            summary_length=len(result.insight_summary),
        )
        return {
            "findings": result.findings,
            "insight_summary": result.insight_summary,
            "is_success": True,
        }
