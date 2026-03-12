from typing import Any, Dict

from app.agent.states import InsightState
from app.core.logger import logger


class DataFetcher:
    """判断现有数据是否足够支撑分析计划，记录缺失查询描述。
    当前为简单版：始终判定数据充足，返回空列表。
    实际补充查询执行逻辑由路由层处理。
    """

    async def __call__(self, state: InsightState) -> Dict[str, Any]:
        logger.info(
            "data_fetcher.start",
            plan_count=len(state.analysis_plan),
            row_count=len(state.query_output),
        )
        logger.info("data_fetcher.completed", supplemental_count=0)
        return {"supplemental_queries": []}
