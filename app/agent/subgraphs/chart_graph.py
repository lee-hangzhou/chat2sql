# NOTE: ChartAdvisor.__call__ 目前依赖 NL2SQLState，与 ChartState 存在以下不兼容字段：
#   - state.sql_result.sql        → ChartState 中缺失，用于 _has_aggregate 判断及 LLM prompt
#   - state.intent_parse_result   → ChartState 中缺失，用于 wants_chart / chart_preference
#   - state.summarized_messages / state.messages → ChartState 用 user_question: str 替代
#
# 待决方案（请选择后告知）：
#   方案 A：修改 ChartAdvisor 使其兼容 ChartState（推荐）
#   方案 B：在此文件写适配器节点，ChartState → ChartAdvisor 所需参数
#   方案 C：在 ChartState 补充 sql / wants_chart / chart_preference 字段，保持 ChartAdvisor 不变
from typing import Any, Dict, List, Literal, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.agent.nodes.chart_advisor import ChartAdvisor

CHART_ADVISOR = "chart_advisor"


class ChartState(BaseModel):
    """
    图表子图状态，用于独立驱动 ChartAdvisor 节点
    """
    execute_result: List[Dict[str, Any]] = Field(default_factory=list, description="待可视化的数据")
    user_question: str = Field(default="", description="用户问题，用于图表标题推断")
    chart_mode: Literal["normal", "insight"] = Field(default="normal", description="图表模式，normal 为普通查询，insight 为洞察模式")
    anomaly_highlights: List[Dict[str, Any]] = Field(default_factory=list, description="insight 模式下的异常点标注")
    chart_option: Optional[Dict[str, Any]] = Field(default=None, description="输出的 ECharts option JSON")
    chart_message: Optional[str] = Field(default=None, description="图表生成失败原因")
    is_success: Optional[bool] = Field(default=None, description="图表生成是否成功")


def build_chart_graph() -> CompiledStateGraph:
    """构建图表子图，START → CHART_ADVISOR → END"""
    graph = StateGraph(ChartState)

    graph.add_node(CHART_ADVISOR, ChartAdvisor())

    graph.add_edge(START, CHART_ADVISOR)
    graph.add_edge(CHART_ADVISOR, END)

    return graph.compile()
