import asyncio
from typing import Any, Dict, List, Optional, Tuple

import sqlglot
from sqlglot import exp
from tortoise.exceptions import OperationalError

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.database import business_db
from app.core.logger import logger
from app.schemas.agent import (
    AgentErrorCode, ExecuteExplainResult, Explain,
    PerformanceResult, SQLResult, SyntaxResult, ValidatedCandidate,
)


class SQLValidator:
    """校验 SQL 候选：语法检查、EXPLAIN 验证、性能分析"""

    _SYSTEM_ERROR_CODES = frozenset({
        1040,  # Too many connections
        1041,  # Out of memory
        1042,  # Can't get hostname for your address
        1043,  # Bad handshake
        1044,  # Access denied for user to database
        1045,  # Access denied for user (using password)
        1080,  # Forcing close of thread
        1152,  # Aborted connection
        1153,  # Got a packet bigger than max_allowed_packet
        1154,  # Got a read error from the connection pipe
        1155,  # Got a write error from the connection pipe
        1156,  # Got timeout from master
        1157,  # Net packets out of order
        1158,  # Couldn't uncompress communication packet
        1159,  # Got timeout reading communication packets
        1160,  # Got error writing communication packets
        1161,  # Got timeout writing communication packets
    })

    _JOIN_TYPE_ALL = "ALL"
    _JOIN_TYPE_INDEX = "index"

    _EXTRA_USING_TEMPORARY = "Using temporary"
    _EXTRA_USING_FILESORT = "Using filesort"
    _EXTRA_USING_JOIN_BUFFER = "Using join buffer"

    _ISSUE_FULL_TABLE_SCAN = "表 {table} 全表扫描，预估扫描行数 {rows}"
    _ISSUE_FULL_INDEX_SCAN = "表 {table} 全索引扫描，预估扫描行数 {rows}"
    _ISSUE_TEMP_AND_FILESORT = "表 {table} 同时使用了临时表和文件排序"
    _ISSUE_JOIN_BUFFER = "表 {table} JOIN 未使用索引"
    _ISSUE_CARTESIAN_PRODUCT = "多表全表扫描（{count} 张表），存在笛卡尔积风险"

    def __init__(self):
        self.db = business_db

    @staticmethod
    def _parse_syntax(sql: str) -> SyntaxResult:
        """使用 sqlglot 校验 SQL 语法，非 SELECT 视为失败"""
        try:
            ast = sqlglot.parse_one(sql)
        except Exception as e:
            return SyntaxResult(is_ok=False, error=f"Syntax Error: {e}")
        if not isinstance(ast, exp.Select):
            return SyntaxResult(is_ok=False, error=AgentErrorCode.ONLY_SELECT.message)
        return SyntaxResult(is_ok=True)

    @staticmethod
    def _extract_error_code(e: OperationalError) -> Optional[int]:
        """从 Tortoise OperationalError 中提取 MySQL 错误码"""
        if not e.args:
            return None
        original = e.args[0]
        if isinstance(original, Exception) and original.args and isinstance(original.args[0], int):
            return original.args[0]
        return None

    async def _execute_explain(self, sql: str) -> ExecuteExplainResult:
        """执行 EXPLAIN，系统级错误向上抛出，SQL 级错误包装为 error 返回"""
        try:
            conn = self.db.get_connection()
            _, rows = await conn.execute_query(f"EXPLAIN {sql}")
            explains = [
                Explain.model_validate({k.lower(): v for k, v in row.items() if v is not None})
                for row in rows
            ]
            return ExecuteExplainResult(explains=explains)
        except OperationalError as e:
            error_code = self._extract_error_code(e)
            if error_code is not None and error_code in self._SYSTEM_ERROR_CODES:
                raise
            return ExecuteExplainResult(error=str(e))

    def _parse_explain(self, explain_result: ExecuteExplainResult) -> PerformanceResult:
        """分析 EXPLAIN 执行计划，检测全表扫描、笛卡尔积等性能问题"""
        issues: list[str] = []
        max_rows = settings.EXPLAIN_MAX_ROWS
        all_scan_count = 0

        for row in explain_result.explains:
            if not row.table:
                continue
            if row.join_type == self._JOIN_TYPE_ALL and row.rows > max_rows:
                issues.append(self._ISSUE_FULL_TABLE_SCAN.format(table=row.table, rows=row.rows))
            if row.join_type == self._JOIN_TYPE_INDEX and row.rows > max_rows:
                issues.append(self._ISSUE_FULL_INDEX_SCAN.format(table=row.table, rows=row.rows))
            if self._EXTRA_USING_TEMPORARY in row.extra and self._EXTRA_USING_FILESORT in row.extra:
                issues.append(self._ISSUE_TEMP_AND_FILESORT.format(table=row.table))
            if self._EXTRA_USING_JOIN_BUFFER in row.extra:
                issues.append(self._ISSUE_JOIN_BUFFER.format(table=row.table))
            if row.join_type == self._JOIN_TYPE_ALL:
                all_scan_count += 1

        if all_scan_count > 1:
            issues.append(self._ISSUE_CARTESIAN_PRODUCT.format(count=all_scan_count))

        explains_str = "\n".join(
            row.model_dump_json(by_alias=True, exclude_none=True)
            for row in explain_result.explains
        )
        return PerformanceResult(is_ok=len(issues) == 0, issues=issues, explains=explains_str)

    async def _validate_single(
        self, sql: str,
    ) -> Tuple[SyntaxResult, Optional[ExecuteExplainResult], Optional[PerformanceResult]]:
        """对单条 SQL 依次执行语法、EXPLAIN、性能校验，前一步失败则后续跳过"""
        syntax = self._parse_syntax(sql)
        if not syntax.is_ok:
            return syntax, None, None
        explain_result = await self._execute_explain(sql)
        if explain_result.error:
            return syntax, explain_result, None
        performance = self._parse_explain(explain_result)
        return syntax, explain_result, performance

    def _classify_results(
        self,
        candidates: List[SQLResult],
        validation_results: List[Tuple[SyntaxResult, Optional[ExecuteExplainResult], Optional[PerformanceResult]]],
    ) -> Tuple[List[ValidatedCandidate], Optional[str], Optional[str]]:
        """将校验结果分类为合法候选与首个各类错误"""
        valid: List[ValidatedCandidate] = []
        first_syntax_error: Optional[str] = None
        first_explain_error: Optional[str] = None

        for i, (syntax, explain, perf) in enumerate(validation_results):
            sql = candidates[i].sql
            if not syntax.is_ok:
                if first_syntax_error is None:
                    first_syntax_error = syntax.error
                continue
            if explain and explain.error:
                if first_explain_error is None:
                    first_explain_error = explain.error
                continue
            valid.append(ValidatedCandidate(sql=sql, explains=explain.explains))

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
