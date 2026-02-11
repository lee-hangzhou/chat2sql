from typing import Dict, Any, Optional

import sqlglot
from sqlglot import exp
from tortoise.exceptions import OperationalError

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.database import business_db
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode, ExecuteExplainResult, Explain, PerformanceResult, SyntaxResult


class SQLValidator:

    # SQL 层面的错误码：可通过重新生成 SQL 来修复
    _SQL_ERROR_CODES = frozenset({
        1054,  # Unknown column
        1064,  # SQL syntax error
        1052,  # Column is ambiguous
        1109,  # Unknown table in field list
        1146,  # Table doesn't exist
        1176,  # Key column doesn't exist in table
    })

    # EXPLAIN join_type 常量
    _JOIN_TYPE_ALL = "ALL"
    _JOIN_TYPE_INDEX = "index"

    # EXPLAIN extra 关键标记
    _EXTRA_USING_TEMPORARY = "Using temporary"
    _EXTRA_USING_FILESORT = "Using filesort"
    _EXTRA_USING_JOIN_BUFFER = "Using join buffer"

    # 性能问题描述
    _ISSUE_FULL_TABLE_SCAN = "表 {table} 全表扫描，预估扫描行数 {rows}"
    _ISSUE_FULL_INDEX_SCAN = "表 {table} 全索引扫描，预估扫描行数 {rows}"
    _ISSUE_TEMP_AND_FILESORT = "表 {table} 同时使用了临时表和文件排序"
    _ISSUE_JOIN_BUFFER = "表 {table} JOIN 未使用索引"
    _ISSUE_CARTESIAN_PRODUCT = "多表全表扫描（{count} 张表），存在笛卡尔积风险"

    def __init__(self):
        self.db = business_db

    @staticmethod
    def _parse_syntax(sql: str) -> SyntaxResult:
        try:
            ast = sqlglot.parse_one(sql)
        except Exception as e:
            err = f"Syntax Error: {e}"
            return SyntaxResult(
                is_ok=False,
                error=err
            )

        if not isinstance(ast, exp.Select):
            return SyntaxResult(
                is_ok=False,
                error=AgentErrorCode.ONLY_SELECT.message,
            )

        return SyntaxResult(
            is_ok=True,
        )

    @staticmethod
    def _extract_error_code(e: OperationalError) -> Optional[int]:
        """从 Tortoise OperationalError 中提取 MySQL 错误码
        """
        if not e.args:
            return None
        original = e.args[0]
        if isinstance(original, Exception) and original.args and isinstance(original.args[0], int):
            return original.args[0]
        return None

    async def _execute_explain(self, sql: str) -> ExecuteExplainResult:
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
            if error_code in self._SQL_ERROR_CODES:
                # SQL 层面错误，记录后交由上游节点重新生成 SQL
                return ExecuteExplainResult(error=str(e))
            # 系统层面错误（权限、连接、配置等），向上抛出
            raise

    def _parse_explain(self, explain_result: ExecuteExplainResult) -> PerformanceResult:
        """分析 EXPLAIN 执行计划，校验是否存在性能问题"""
        issues: list[str] = []
        max_rows = settings.EXPLAIN_MAX_ROWS
        all_scan_count = 0

        for row in explain_result.explains:
            # 跳过不涉及实际表的行（如 SELECT 1、SELECT NOW()）
            if not row.table:
                continue

            # 全表扫描 + 行数超阈值
            if row.join_type == self._JOIN_TYPE_ALL and row.rows > max_rows:
                issues.append(self._ISSUE_FULL_TABLE_SCAN.format(table=row.table, rows=row.rows))

            # 全索引扫描 + 行数超阈值
            if row.join_type == self._JOIN_TYPE_INDEX and row.rows > max_rows:
                issues.append(self._ISSUE_FULL_INDEX_SCAN.format(table=row.table, rows=row.rows))

            # extra 标记检查
            if self._EXTRA_USING_TEMPORARY in row.extra and self._EXTRA_USING_FILESORT in row.extra:
                issues.append(self._ISSUE_TEMP_AND_FILESORT.format(table=row.table))
            if self._EXTRA_USING_JOIN_BUFFER in row.extra:
                issues.append(self._ISSUE_JOIN_BUFFER.format(table=row.table))

            # 统计全表扫描的表数量
            if row.join_type == self._JOIN_TYPE_ALL:
                all_scan_count += 1

        # 多表全表扫描 → 笛卡尔积风险
        if all_scan_count > 1:
            issues.append(self._ISSUE_CARTESIAN_PRODUCT.format(count=all_scan_count))

        explains_str = "\n".join(
            row.model_dump_json(by_alias=True, exclude_none=True)
            for row in explain_result.explains
        )

        return PerformanceResult(
            is_ok=len(issues) == 0,
            issues=issues,
            explains=explains_str,
        )

    @staticmethod
    def _build_fail_result(
            state: NL2SQLState,
        syntax_result: SyntaxResult,
        explain_error: Optional[str],
        performance_result: Optional[PerformanceResult],
        error_message: str,
    ) -> Dict[str, Any]:
        """构建校验失败的返回值，达到重试上限时附加终态标记"""
        new_retry_count = state.retry_count + 1
        result: Dict[str, Any] = {
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
        if not state.sql_result or not state.sql_result.sql:
            logger.warning("sql_validator.no_sql")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        sql = state.sql_result.sql
        logger.info("sql_validator.start", retry_count=state.retry_count)

        # 1. 语法校验
        syntax_result = self._parse_syntax(sql)
        if not syntax_result.is_ok:
            logger.warning("sql_validator.syntax_failed", error=syntax_result.error)
            return self._build_fail_result(
                state, syntax_result, None, None, syntax_result.error,
            )

        # 2. 执行 EXPLAIN
        explain_result = await self._execute_explain(sql)
        if explain_result.error:
            logger.warning("sql_validator.explain_failed", error=explain_result.error)
            return self._build_fail_result(
                state, syntax_result, explain_result.error, None, explain_result.error,
            )

        # 3. 性能校验
        performance_result = self._parse_explain(explain_result)
        if not performance_result.is_ok:
            logger.warning(
                "sql_validator.performance_issues",
                issues=performance_result.issues,
            )
            return self._build_fail_result(
                state, syntax_result, None, performance_result,
                "; ".join(performance_result.issues),
            )

        logger.info("sql_validator.passed")
        return {
            "syntax_result": syntax_result,
            "explain_error": None,
            "performance_result": performance_result,
        }
