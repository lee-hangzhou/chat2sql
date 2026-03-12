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

_MAX_RETRY_COUNT = 2


class _HypothesisResult(BaseModel):
    hypotheses: List[str] = Field(default_factory=list, description="生成的原因假设列表")
    validated_hypotheses: List[str] = Field(default_factory=list, description="经数据验证合理的假设列表")


class HypothesisGenerator:
    """基于异常点生成原因假设，并用数据验证每个假设的合理性"""

    def __init__(self):
        self.structured_llm = (
            llm.with_structured_output(_HypothesisResult)
            .with_retry(
                stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
                wait_exponential_jitter=True,
            )
        )

    @staticmethod
    def _build_anomaly_text(anomalies: List[Dict[str, Any]]) -> str:
        if not anomalies:
            return "(无异常点)"
        return json.dumps(anomalies, ensure_ascii=False, default=str)

    @staticmethod
    def _build_sample(rows: List[Dict[str, Any]], n: int = 5) -> str:
        if not rows:
            return "(empty)"
        return json.dumps(rows[:n], ensure_ascii=False, default=str)

    async def __call__(self, state: InsightState) -> Dict[str, Any]:
        retry_count = state.hypothesis_retry_count

        logger.info(
            "hypothesis_generator.start",
            anomaly_count=len(state.anomalies),
            retry_count=retry_count,
        )

        if retry_count >= _MAX_RETRY_COUNT:
            logger.info("hypothesis_generator.max_retry_reached", retry_count=retry_count)
            return {
                "hypotheses": state.hypotheses,
                "validated_hypotheses": state.validated_hypotheses,
                "hypothesis_retry_count": retry_count + 1,
            }

        if not state.anomalies:
            logger.warning("hypothesis_generator.no_anomalies")
            return {
                "hypotheses": [],
                "validated_hypotheses": [],
                "hypothesis_retry_count": retry_count + 1,
            }

        anomaly_text = self._build_anomaly_text(state.anomalies)
        sample = self._build_sample(state.query_output)

        system_prompt = (
            "你是一位数据分析专家，擅长从数据异常中推断业务原因。\n"
            "任务：\n"
            "1. 根据提供的异常点，生成 3-5 个可能的原因假设（hypotheses）\n"
            "2. 结合数据样例，判断哪些假设有数据支撑，输出验证通过的假设（validated_hypotheses）\n"
            "要求：每条假设为一句完整的中文描述，指出可能的业务或数据原因。\n"
            "输出 JSON，字段：hypotheses（所有假设），validated_hypotheses（有数据支撑的假设）。"
        )
        human_prompt = (
            "检测到的异常点：\n{anomaly_text}\n\n"
            "数据样例（前 {sample_count} 行）：\n{sample}"
        )

        messages = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ]).format_messages(
            anomaly_text=anomaly_text,
            sample_count=min(5, len(state.query_output)),
            sample=sample,
        )

        try:
            async with log_elapsed(logger, "hypothesis_generator.llm_completed"):
                result: _HypothesisResult = await self.structured_llm.ainvoke(messages)
        except Exception as e:
            logger.error("hypothesis_generator.llm_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.LLM_ERROR,
                "error_message": AgentErrorCode.LLM_ERROR.message,
            }

        logger.info(
            "hypothesis_generator.completed",
            hypotheses_count=len(result.hypotheses),
            validated_count=len(result.validated_hypotheses),
        )
        return {
            "hypotheses": result.hypotheses,
            "validated_hypotheses": result.validated_hypotheses,
            "hypothesis_retry_count": retry_count + 1,
        }
