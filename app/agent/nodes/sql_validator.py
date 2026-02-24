import asyncio
from typing import Any, Dict, List, Optional, Tuple

import sqlglot
from sqlglot import exp
from sqlalchemy.exc import OperationalError

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.database import business_db
from app.core.dialect import ExplainAnalysis
from app.core.logger import logger
from app.schemas.agent import (
    AgentErrorCode, PerformanceResult, SQLResult, SyntaxResult, ValidatedCandidate,
)


class SQLValidator:
    """校验 SQL 候选：语法检查、EXPLAIN 验证、性能分析"""

    def __init__(self):
        self.db = business_db
        self.dialect = business_db.dialect

    def _parse_syntax(self, sql: str) -> SyntaxResult:
        """使用 sqlglot 校验 SQL 语法，非 SELECT 视为失败"""
        try:
            ast = sqlglot.parse_one(sql, dialect=self.dialect.sqlglot_dialect)
        except Exception as e:
            return SyntaxResult(is_ok=False, error=f"Syntax Error: {e}")
        if not isinstance(ast, exp.Select):
            return SyntaxResult(is_ok=False, error=AgentErrorCode.ONLY_SELECT.message)
        return SyntaxResult(is_ok=True)

    async def _execute_explain(self, sql: str) -> Tuple[Optional[ExplainAnalysis], Optional[str]]:
        """执行 EXPLAIN，返回分析结果或错误信息；系统级错误向上抛出"""
        explain_sql = self.dialect.build_explain_sql(sql)
        try:
            rows = await self.db.execute_query(explain_sql)
            analysis = self.dialect.parse_explain(rows, settings.EXPLAIN_MAX_ROWS)
            return analysis, None
        except OperationalError as e:
            if self.dialect.is_system_error(e):
                raise
            return None, str(e)

    async def _validate_single(
        self, sql: str,
    ) -> Tuple[SyntaxResult, Optional[ExplainAnalysis], Optional[str]]:
        """对单条 SQL 依次执行语法、EXPLAIN 校验，前一步失败则后续跳过"""
        syntax = self._parse_syntax(sql)
        if not syntax.is_ok:
            return syntax, None, None
        analysis, error = await self._execute_explain(sql)
        if error:
            return syntax, None, error
        return syntax, analysis, None

    def _classify_results(
        self,
        candidates: List[SQLResult],
        validation_results: List[Tuple[SyntaxResult, Optional[ExplainAnalysis], Optional[str]]],
    ) -> Tuple[List[ValidatedCandidate], Optional[str], Optional[str]]:
        """将校验结果分类为合法候选与首个各类错误"""
        valid: List[ValidatedCandidate] = []
        first_syntax_error: Optional[str] = None
        first_explain_error: Optional[str] = None

        for i, (syntax, analysis, explain_error) in enumerate(validation_results):
            sql = candidates[i].sql
            if not syntax.is_ok:
                if first_syntax_error is None:
                    first_syntax_error = syntax.error
                continue
            if explain_error:
                if first_explain_error is None:
                    first_explain_error = explain_error
                continue
            valid.append(ValidatedCandidate(sql=sql, explain=analysis))

        return valid, first_syntax_error, first_explain_error

    def _build_all_failed_result(
        self,
        state: NL2SQLState,
        first_syntax_error: Optional[str],
        first_explain_error: Optional[str],
    ) -> Dict[str, Any]:
        """所有候选校验失败时，根据首个错误类型构建重试或终态结果"""
        if first_syntax_error:
            return self._build_fail_result(
                state,
                SyntaxResult(is_ok=False, error=first_syntax_error),
                None, None, first_syntax_error,
            )
        if first_explain_error:
            return self._build_fail_result(
                state,
                SyntaxResult(is_ok=True),
                first_explain_error, None, first_explain_error,
            )
        return {
            "validated_candidates": [],
            "is_success": False,
            "error_code": AgentErrorCode.VALIDATION_ALL_FAILED,
            "error_message": AgentErrorCode.VALIDATION_ALL_FAILED.message,
        }

    @staticmethod
    def _build_fail_result(
        state: NL2SQLState,
        syntax_result: SyntaxResult,
        explain_error: Optional[str],
        performance_result: Optional[PerformanceResult],
        error_message: str,
    ) -> Dict[str, Any]:
        """构建单类错误的校验失败结果，达到重试上限时附加终态标记"""
        new_retry_count = state.retry_count + 1
        result: Dict[str, Any] = {
            "validated_candidates": [],
            "syntax_result": syntax_result,
            "explain_error": explain_error,
            "performance_result": performance_result,
            "retry_count": new_retry_count,
        }
        if new_retry_count >= settings.AGENT_MAX_RETRIES:
            result["is_success"] = False
            result["error_code"] = AgentErrorCode.VALIDATION_RETRY_LIMIT
            result["error_message"] = error_message
        return result

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        """并发校验所有候选 SQL，输出合法候选列表或按首个错误类型构建重试结果"""
        candidates = state.sql_candidates
        if not candidates:
            logger.warning("sql_validator.no_candidates")
            return {
                "validated_candidates": [],
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        logger.info("sql_validator.start", candidate_count=len(candidates), retry_count=state.retry_count)

        validation_results = await asyncio.gather(
            *(self._validate_single(c.sql) for c in candidates)
        )
        valid, first_syntax_error, first_explain_error = self._classify_results(candidates, validation_results)

        if not valid:
            logger.warning("sql_validator.all_candidates_failed", candidate_count=len(candidates))
            return self._build_all_failed_result(state, first_syntax_error, first_explain_error)

        logger.info("sql_validator.passed", valid_count=len(valid))
        return {
            "validated_candidates": valid,
            "syntax_result": SyntaxResult(is_ok=True),
            "explain_error": None,
            "performance_result": PerformanceResult(is_ok=True, issues=[]),
        }
