from typing import Any, Dict, List

from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.database import business_db
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
            return {
                "is_success": False,
                "error_code": AgentErrorCode.NO_SQL,
                "error_message": AgentErrorCode.NO_SQL.message,
            }

        try:
            result = await self._execute_sql(state.sql_result.sql)
        except Exception as e:
            return {
                "is_success": False,
                "error_code": AgentErrorCode.EXECUTION_ERROR,
                "error_message": str(e),
            }

        # 截断过大结果集，防止内存溢出
        if len(result) > settings.EXECUTOR_MAX_ROWS:
            result = result[:settings.EXECUTOR_MAX_ROWS]

        return {"execute_result": result, "is_success": True}
