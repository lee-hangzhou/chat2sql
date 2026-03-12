from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.insight import (
    AnomalyDetector,
    DataFetcher,
    HypothesisGenerator,
    InsightPlanner,
    InsightSummarizer,
)
from app.agent.states import InsightState

INSIGHT_PLANNER = "insight_planner"
DATA_FETCHER = "data_fetcher"
ANOMALY_DETECTOR = "anomaly_detector"
HYPOTHESIS_GENERATOR = "hypothesis_generator"
INSIGHT_SUMMARIZER = "insight_summarizer"


def route_after_insight_planner(state: InsightState) -> str:
    if state.is_success is False:
        return END
    return DATA_FETCHER


def route_after_data_fetcher(state: InsightState) -> str:
    """supplemental_queries 非空时简化版仍继续到 ANOMALY_DETECTOR（不真正执行补充查询）"""
    if state.is_success is False:
        return END
    return ANOMALY_DETECTOR


def route_after_anomaly_detector(state: InsightState) -> str:
    if state.is_success is False:
        return END
    return HYPOTHESIS_GENERATOR


def route_after_hypothesis_generator(state: InsightState) -> str:
    """无验证假设且未超重试上限 → 重试；否则 → 汇总"""
    if state.is_success is False:
        return END
    if not state.validated_hypotheses and state.hypothesis_retry_count < 2:
        return HYPOTHESIS_GENERATOR
    return INSIGHT_SUMMARIZER


def build_insight_graph() -> CompiledStateGraph:
    """构建 Insight 分析子图"""
    graph = StateGraph(InsightState)

    graph.add_node(INSIGHT_PLANNER, InsightPlanner())
    graph.add_node(DATA_FETCHER, DataFetcher())
    graph.add_node(ANOMALY_DETECTOR, AnomalyDetector())
    graph.add_node(HYPOTHESIS_GENERATOR, HypothesisGenerator())
    graph.add_node(INSIGHT_SUMMARIZER, InsightSummarizer())

    graph.add_edge(START, INSIGHT_PLANNER)
    graph.add_conditional_edges(INSIGHT_PLANNER, route_after_insight_planner)
    graph.add_conditional_edges(DATA_FETCHER, route_after_data_fetcher)
    graph.add_conditional_edges(ANOMALY_DETECTOR, route_after_anomaly_detector)
    graph.add_conditional_edges(HYPOTHESIS_GENERATOR, route_after_hypothesis_generator)
    graph.add_edge(INSIGHT_SUMMARIZER, END)

    return graph.compile()
