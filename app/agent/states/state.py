from typing import Any, Annotated, Dict, List, Optional

from langchain_core.messages import AnyMessage, BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

from app.agent.states.chart import ChartState
from app.agent.states.insight import InsightState
from app.agent.states.query import QueryState
from app.schemas.agent import (
    AgentErrorCode, IntentParseResult,
)


def merge_schemas(existing: List[str], new: List[str]) -> List[str]:
    return list(dict.fromkeys(existing + new))


class NL2SQLState(BaseModel):
    """
    NL2SQL全局状态，记录用户输入、意图解析、SQL生成及执行情况
    """
    user_id: Optional[str] = Field(default=None, description="用户标识，由调用方注入，用于审计")
    intent_parse_result: Optional[IntentParseResult] = Field(default=None, description="格式化的意图解析")
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list, description="对话消息记录")
    summarized_messages: List[AnyMessage] = Field(default_factory=list,
                                                  description="摘要后的消息列表，由 SummarizationNode 写入，LLM 节点从此读取")
    context: Dict[str, Any] = Field(default_factory=dict,
                                    description="SummarizationNode 运行时上下文，存储 RunningSummary")

    query_state: QueryState = Field(default_factory=QueryState, description="查询状态")
    insight_state: InsightState = Field(default_factory=InsightState, description="洞察状态")
    chart_state: ChartState = Field(default_factory=ChartState, description="图表状态")

    # 终态（由 sql_validator / executor 写入）
    is_success: Optional[bool] = Field(default=None, description="最终执行是否成功")
    error_code: Optional[AgentErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败时的错误描述")

