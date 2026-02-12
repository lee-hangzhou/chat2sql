import asyncio
from typing import Any, Dict, List

import sqlglot
from sqlglot import exp

from app.agent.states import NL2SQLState
from app.core.database import business_db
from app.core.logger import logger
from app.schemas.agent import (
    AgentErrorCode, CandidateExecResult, Explain, SQLResult, ValidatedCandidate,
)
from app.utils.timing import log_elapsed


class SQLSelector:
    """从校验通过的候选中选出最优 SQL"""

    _COMPARE_LIMIT = 50

    def __init__(self):
        self.db = business_db

    @staticmethod
    def _ensure_deterministic_sample(sql: str, limit: int) -> str:
        """为 SQL 注入确定性 ORDER BY 并添加/收紧 LIMIT，确保样本可比"""
        try:
            tree = sqlglot.parse_one(sql, dialect="mysql")

            if not tree.args.get("order"):
                select_exprs = tree.args.get("expressions", [])
                order_cols = []
                for i, col in enumerate(select_exprs, start=1):
                    order_cols.append(
                        exp.Ordered(this=exp.Literal.number(i), desc=False)
                    )
                if order_cols:
                    tree.set("order", exp.Order(expressions=order_cols))

            existing_limit = tree.args.get("limit")
            if existing_limit:
                existing_val = int(existing_limit.expression.this)
                if existing_val <= limit:
                    return tree.sql(dialect="mysql")
            tree.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
            return tree.sql(dialect="mysql")
        except Exception as e:
            logger.warning("sql_selector.ensure_deterministic_sample_failed", sql=sql, error=str(e))
            return sql

    async def _execute_for_comparison(self, sql: str) -> list[dict] | None:
        """注入确定性排序和 LIMIT 后执行单条 SQL 获取样本结果，失败返回 None"""
        limited_sql = self._ensure_deterministic_sample(sql, self._COMPARE_LIMIT)
        try:
            conn = self.db.get_connection()
            _, rows = await conn.execute_query(limited_sql)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("sql_selector.comparison_execution_failed", error=str(e))
            return None

    @staticmethod
    def _results_equivalent(a: list[dict], b: list[dict]) -> bool:
        """比较两个结果集是否等价，忽略行序、列序和别名"""
        if len(a) != len(b):
            return False

        def normalize(rows: list[dict]) -> list[tuple]:
            return sorted(
                tuple(sorted(str(v) for v in row.values()))
                for row in rows
            )

        return normalize(a) == normalize(b)

    @staticmethod
    def _explain_cost(explains: List[Explain]) -> int:
        """EXPLAIN 预估总扫描行数，作为开销度量"""
        return sum(e.rows for e in explains)

    async def _execute_candidates(
        self, candidates: List[ValidatedCandidate],
    ) -> List[CandidateExecResult]:
        """并发执行所有候选，过滤执行失败的，返回带结果的候选列表"""
        tasks = [self._execute_for_comparison(c.sql) for c in candidates]
        results = await asyncio.gather(*tasks)
        return [
            CandidateExecResult(
                sql=candidates[i].sql,
                explains=candidates[i].explains,
                exec_result=results[i],
            )
            for i in range(len(candidates))
            if results[i] is not None
        ]

    def _find_majority(self, entries: List[CandidateExecResult]) -> CandidateExecResult | None:
        """按结果集分组投票，返回多数组中开销最低的候选，无多数返回 None"""
        groups: list[list[int]] = []
        for i, entry in enumerate(entries):
            placed = False
            for group in groups:
                if self._results_equivalent(entry.exec_result, entries[group[0]].exec_result):
                    group.append(i)
                    placed = True
                    break
            if not placed:
                groups.append([i])

        majority = max(groups, key=len)
        if len(majority) <= 1 < len(groups):
            return None

        group_entries = [entries[i] for i in majority]
        return min(group_entries, key=lambda e: self._explain_cost(e.explains))

    def _select_winner(
        self,
        all_results: List[CandidateExecResult],
        has_previous: bool,
    ) -> Dict[str, Any]:
        """单条直接选；多条投票选多数；无多数首次请求仲裁，仲裁后仍无多数则交由 judge"""
        if len(all_results) == 1:
            logger.info("sql_selector.single_candidate")
            return {
                "sql_result": SQLResult(sql=all_results[0].sql),
                "candidate_exec_results": all_results,
            }

        winner = self._find_majority(all_results)
        if winner:
            logger.info("sql_selector.majority_found")
            return {
                "sql_result": SQLResult(sql=winner.sql),
                "candidate_exec_results": all_results,
            }

        if not has_previous:
            logger.info("sql_selector.results_inconsistent", count=len(all_results))
            return {
                "candidate_exec_results": all_results,
                "needs_arbitration": True,
            }

        logger.info("sql_selector.no_majority_after_arbitration")
        return {"candidate_exec_results": all_results}

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        new_candidates = state.validated_candidates
        previous_results = list(state.candidate_exec_results)

        if not new_candidates and not previous_results:
            logger.warning("sql_selector.no_candidates")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        async with log_elapsed(logger, "sql_selector.execution_completed") as ctx:
            new_results = await self._execute_candidates(new_candidates)
            ctx["new_executed"] = len(new_results)

        all_results = previous_results + new_results

        if not all_results:
            logger.warning("sql_selector.all_execution_failed")
            if new_candidates:
                winner = min(new_candidates, key=lambda c: self._explain_cost(c.explains))
                return {"sql_result": SQLResult(sql=winner.sql)}
            return {
                "is_success": False,
                "error_code": AgentErrorCode.EXECUTION_ERROR,
                "error_message": AgentErrorCode.EXECUTION_ERROR.message,
            }

        return self._select_winner(all_results, has_previous=bool(previous_results))
