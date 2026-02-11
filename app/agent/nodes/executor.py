from typing import Any, Dict, List

from app.agent.states import NL2SQLState
from app.core import Singleton, logger
from app.core.database import business_db


class Executor(Singleton):
    """执行验证通过的 SQL，返回原始查询结果"""

    def __init__(self):
        self.db = business_db

    async def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        _, rows = await conn.execute_query(sql)
        return [dict(row) for row in rows]

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        result = await self._execute_sql(state.sql_result.sql)
        logger.info()
        return {"execute_result": result}
