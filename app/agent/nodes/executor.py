import time
from typing import Any, Dict, List

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.database import business_db
from app.core.logger import logger
from app.schemas.agent import AgentErrorCode


class Executor:
    """执行验证通过的 SQL，返回原始查询结果"""

    def __init__(self):
        self.db = business_db

    async def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        _, rows = await conn.execute_query(sql)
        return [dict(row) for row in rows]

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        if not state.sql_result or not state.sql_result.sql:
            logger.warning("executor.no_sql")
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        sql = state.sql_result.sql
        logger.info("executor.start")

        try:
            start = time.monotonic()
            result = await self._execute_sql(sql)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(
                "executor.query_completed",
                elapsed_ms=round(elapsed_ms, 1),
                row_count=len(result),
            )
        except Exception as e:
            logger.error("executor.query_failed", error=str(e))
            return {
                "is_success": False,
                "error_code": AgentErrorCode.EXECUTION_ERROR,
                "error_message": str(e),
            }

        truncated = len(result) > settings.EXECUTOR_MAX_ROWS
        if truncated:
            result = result[:settings.EXECUTOR_MAX_ROWS]
            logger.info(
                "executor.result_truncated",
                max_rows=settings.EXECUTOR_MAX_ROWS,
            )

        logger.info("executor.completed")
        return {"execute_result": result, "is_success": True}
