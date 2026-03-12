import json
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import sqlglot
from sqlglot import exp

from app.agent.prompts import ChatPrompt
from app.core.config import settings
from app.core.database import business_db
from app.core.llm import llm
from app.core.logger import logger
from app.schemas.agent import ChartAdvice, ChartType
from app.utils import chart_builder
from app.utils.timing import log_elapsed
from app.vars.prompts import CHART_USER_PREFERENCE_SECTION, CHART_USER_WANTS_SECTION


@runtime_checkable
class ChartAdvisorState(Protocol):
    """ChartAdvisor 所需的最小 state 协议，NL2SQLState 与 ChartState 均满足"""
    execute_result: Optional[List[Dict[str, Any]]]

_SAMPLE_MAX_ROWS = 3
_UNKNOWN_TYPE = "unknown"
_EMPTY_SAMPLE = "(empty)"

_SKIP_REASON_NON_AGGREGATE = "non_aggregate_skip"


class ChartAdvisor:
    """根据查询结果推荐图表类型并生成 ECharts option"""

    _MSG_EMPTY_RESULT = "查询结果为空，无法生成图表"
    _MSG_NO_NUMERIC = "查询结果中没有数值列，无法生成图表"
    _MSG_LLM_UNAVAILABLE = "图表推荐服务暂时不可用"
    _MSG_NOT_SUITABLE = "当前数据不适合图表展示"
    _MSG_BUILD_FAILED = "图表生成失败"
    _MSG_FIELD_NOT_FOUND = "推荐的{}字段 '{}' 不存在于查询结果中"

    def __init__(self):
        self.structured_llm = llm.with_structured_output(ChartAdvice).with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )
        self.dialect = business_db.dialect

    async def __call__(self, state: ChartAdvisorState) -> Dict[str, Any]:
        rows = state.execute_result or []
        sql_result = getattr(state, "sql_result", None)
        sql = sql_result.sql if sql_result else ""
        intent = getattr(state, "intent_parse_result", None)
        user_wants = intent.wants_chart if intent else None
        # insight 模式视为用户明确需要图表
        if getattr(state, "chart_mode", "normal") == "insight":
            user_wants = True

        skip_reason = self._pre_filter(rows, sql, user_wants)
        if skip_reason:
            return self._skip_result(skip_reason, user_wants)

        question = self._extract_question(state)
        columns_info = self._build_columns_info(rows)
        sample = self._build_sample(rows)
        preference_section = self._build_preference_section(intent)

        try:
            async with log_elapsed(logger, "chart_advisor.llm_completed"):
                advice: ChartAdvice = await self.structured_llm.ainvoke(
                    ChatPrompt.chart_advisor_prompt(
                        question=question,
                        sql=sql,
                        columns_info=columns_info,
                        row_count=len(rows),
                        sample_rows=sample,
                        user_chart_preference_section=preference_section,
                    )
                )
        except Exception as e:
            logger.warning("chart_advisor.llm_failed", error=str(e))
            return self._none_result(self._MSG_LLM_UNAVAILABLE if user_wants else None)

        if advice.chart_type == ChartType.NONE:
            return self._none_result(self._MSG_NOT_SUITABLE if user_wants else None)

        validation_error = self._validate_fields(advice, rows)
        if validation_error:
            logger.warning("chart_advisor.field_validation_failed", error=validation_error)
            return self._none_result(validation_error if user_wants else None)

        try:
            option = chart_builder.build(advice, rows)
        except Exception as e:
            logger.warning("chart_advisor.build_failed", error=str(e))
            return self._none_result(self._MSG_BUILD_FAILED if user_wants else None)

        logger.info("chart_advisor.completed", chart_type=advice.chart_type.value)
        return {"chart_option": option, "chart_message": None}

    def _pre_filter(
        self,
        rows: List[Dict[str, Any]],
        sql: str,
        user_wants: Optional[bool],
    ) -> Optional[str]:
        """代码前置过滤，返回 None 表示通过，否则返回跳过原因"""
        if not rows:
            return self._MSG_EMPTY_RESULT

        if not self._has_numeric_column(rows[0]):
            return self._MSG_NO_NUMERIC

        if not user_wants and not self._has_aggregate(sql):
            return _SKIP_REASON_NON_AGGREGATE

        return None

    def _skip_result(
        self,
        reason: str,
        user_wants: Optional[bool],
    ) -> Dict[str, Any]:
        if reason == _SKIP_REASON_NON_AGGREGATE:
            return self._none_result(None)
        msg = reason if user_wants else None
        if msg:
            logger.info("chart_advisor.skipped", reason=reason)
        return self._none_result(msg)

    @staticmethod
    def _none_result(message: Optional[str]) -> Dict[str, Any]:
        return {"chart_option": None, "chart_message": message}

    @staticmethod
    def _has_numeric_column(row: Dict[str, Any]) -> bool:
        return any(isinstance(v, (int, float)) for v in row.values())

    def _has_aggregate(self, sql: str) -> bool:
        if not sql:
            return False
        try:
            ast = sqlglot.parse_one(sql, dialect=self.dialect.sqlglot_dialect)
        except Exception:
            return False

        for node in ast.walk():
            if isinstance(node, (exp.AggFunc, exp.Group)):
                return True
        return False

    @staticmethod
    def _extract_question(state: ChartAdvisorState) -> str:
        # ChartState 直接提供 user_question
        user_question = getattr(state, "user_question", None)
        if user_question:
            return user_question
        # NL2SQLState 从消息历史中提取
        messages = getattr(state, "summarized_messages", None) or getattr(state, "messages", [])
        for msg in reversed(messages):
            if msg.type == "human":
                return msg.content
        return ""

    @staticmethod
    def _build_columns_info(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        first_row = rows[0]
        parts = []
        for col, val in first_row.items():
            type_name = type(val).__name__ if val is not None else _UNKNOWN_TYPE
            parts.append(f"{col} ({type_name})")
        return ", ".join(parts)

    @staticmethod
    def _build_sample(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return _EMPTY_SAMPLE
        sample = rows[:_SAMPLE_MAX_ROWS]
        return json.dumps(sample, ensure_ascii=False, default=str)

    @staticmethod
    def _build_preference_section(intent) -> str:
        if not intent:
            return ""
        if intent.wants_chart and intent.chart_preference:
            return CHART_USER_PREFERENCE_SECTION.format(
                chart_preference=intent.chart_preference.value,
            )
        if intent.wants_chart:
            return CHART_USER_WANTS_SECTION
        return ""

    @classmethod
    def _validate_fields(
        cls,
        advice: ChartAdvice,
        rows: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not rows:
            return None
        columns = set(rows[0].keys())

        field_checks = [
            (advice.x_field, "X 轴"),
            (advice.y_field, "Y 轴"),
            (advice.series_field, "分组"),
        ]
        for field_value, field_label in field_checks:
            if field_value and field_value not in columns:
                return cls._MSG_FIELD_NOT_FOUND.format(field_label, field_value)
        return None
