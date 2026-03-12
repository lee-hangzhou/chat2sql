from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.orchestrator import Orchestrator
from app.agent.states import InsightState, OrchestratorState
from app.schemas.agent import OrchestratorIntent
from app.agent.subgraphs.chart_graph import ChartState, build_chart_graph
from app.agent.subgraphs.insight_graph import build_insight_graph
from app.agent.subgraphs.query_graph import build_query_graph
from app.core.config import CheckpointerType, settings
from app.core.llm import llm
from app.core.logger import logger
from app.vars.vars import HUMAN_TYPE

ORCHESTRATOR = "orchestrator"
QUERY_SUBGRAPH = "query_subgraph"
INSIGHT_SUBGRAPH = "insight_subgraph"
CHART_SUBGRAPH = "chart_subgraph"
CHAT = "chat"


def route_after_orchestrator(state: OrchestratorState) -> str:
    if state.is_success is False:
        return END
    intent = state.current_intent
    has_data = bool(state.cached_query_result)
    if intent == OrchestratorIntent.QUERY:
        return QUERY_SUBGRAPH
    if intent == OrchestratorIntent.INSIGHT:
        return INSIGHT_SUBGRAPH if has_data else QUERY_SUBGRAPH
    if intent == OrchestratorIntent.CHART_UPDATE:
        return CHART_SUBGRAPH if has_data else QUERY_SUBGRAPH
    return CHAT


def _last_user_message(messages) -> str:
    for msg in reversed(messages):
        if msg.type == HUMAN_TYPE:
            return str(msg.content)
    return ""


def _make_query_node(query_graph: CompiledStateGraph):
    async def _run(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
        logger.info("query_subgraph.start")
        result = await query_graph.ainvoke({"messages": state.messages}, config)

        # 提取子图新增的消息（排除传入的原始消息）
        all_messages = result.get("messages", [])
        new_messages = all_messages[len(state.messages):]

        # 最后一条 AI 消息作为 final_response
        final_response = None
        for msg in reversed(new_messages):
            if hasattr(msg, "type") and msg.type == "ai":
                final_response = str(msg.content)
                break

        out: Dict[str, Any] = {
            "is_success": result.get("is_success"),
            "error_code": result.get("error_code"),
            "error_message": result.get("error_message"),
        }
        if new_messages:
            out["messages"] = new_messages
        if final_response is not None:
            out["final_response"] = final_response
        if result.get("execute_result"):
            out["query_output"] = result["execute_result"]
            out["cached_query_result"] = result["execute_result"]
        if result.get("chart_option"):
            out["chart_option"] = result["chart_option"]

        logger.info(
            "query_subgraph.completed",
            is_success=out.get("is_success"),
            has_chart=out.get("chart_option") is not None,
        )
        return out

    return _run


def _make_insight_node(insight_graph: CompiledStateGraph):
    async def _run(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
        logger.info("insight_subgraph.start")
        data = state.cached_query_result or state.query_output or []
        user_question = _last_user_message(state.messages)

        result = await insight_graph.ainvoke(
            InsightState(query_output=data, user_question=user_question).model_dump(),
            config,
        )

        insight_summary = result.get("insight_summary") or ""
        findings = result.get("findings", [])
        insight_report: Dict[str, Any] = {
            "summary": insight_summary,
            "findings": [f.model_dump() if hasattr(f, "model_dump") else f for f in findings],
        }

        out: Dict[str, Any] = {
            "insight_report": insight_report,
            "final_response": insight_summary,
            "is_success": result.get("is_success"),
            "error_code": result.get("error_code"),
            "error_message": result.get("error_message"),
        }
        if insight_summary:
            out["messages"] = [AIMessage(content=insight_summary)]

        logger.info("insight_subgraph.completed", findings_count=len(findings))
        return out

    return _run


def _make_chart_node(chart_graph: CompiledStateGraph):
    async def _run(state: OrchestratorState, config: RunnableConfig) -> Dict[str, Any]:
        logger.info("chart_subgraph.start")
        data = state.cached_query_result or state.query_output or []
        user_question = _last_user_message(state.messages)

        result = await chart_graph.ainvoke(
            ChartState(execute_result=data, user_question=user_question).model_dump(),
            config,
        )

        chart_option = result.get("chart_option")
        chart_message = result.get("chart_message")

        reply = chart_message or ("图表已更新" if chart_option else "当前数据暂不适合图表展示")
        out: Dict[str, Any] = {
            "final_response": reply,
            "is_success": True,
            "messages": [AIMessage(
                content=reply,
                additional_kwargs={"chart_option": chart_option} if chart_option else {},
            )],
        }
        if chart_option:
            out["chart_option"] = chart_option

        logger.info("chart_subgraph.completed", has_chart=chart_option is not None)
        return out

    return _run


async def _chat_node(state: OrchestratorState) -> Dict[str, Any]:
    """直接调用 LLM 进行自然语言对话"""
    logger.info("chat_node.start")
    chat_llm = llm.with_retry(
        stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
        wait_exponential_jitter=True,
    )
    try:
        response = await chat_llm.ainvoke(state.messages)
        reply = response.content.strip()
    except Exception as e:
        logger.warning("chat_node.llm_failed", error=str(e))
        reply = "抱歉，我暂时无法响应，请稍后再试。"

    logger.info("chat_node.completed")
    return {
        "final_response": reply,
        "is_success": True,
        "messages": [AIMessage(content=reply)],
    }


@asynccontextmanager
async def create_checkpointer() -> AsyncGenerator[BaseCheckpointSaver, None]:
    """根据配置创建 checkpointer，通过 async context manager 管理连接生命周期"""
    checkpointer_type = settings.CHECKPOINTER_TYPE

    if checkpointer_type == CheckpointerType.SQLITE:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINTER_SQLITE_PATH) as saver:
            yield saver
            return

    if checkpointer_type == CheckpointerType.POSTGRES:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(settings.CHECKPOINTER_POSTGRES_URI) as saver:
            await saver.asetup()
            yield saver
            return

    yield MemorySaver()


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """构建 Orchestrator 主图，checkpointer 由调用方注入"""
    query_graph = build_query_graph()
    insight_graph = build_insight_graph()
    chart_graph = build_chart_graph()

    graph = StateGraph(OrchestratorState)

    graph.add_node(ORCHESTRATOR, Orchestrator())
    graph.add_node(QUERY_SUBGRAPH, _make_query_node(query_graph))
    graph.add_node(INSIGHT_SUBGRAPH, _make_insight_node(insight_graph))
    graph.add_node(CHART_SUBGRAPH, _make_chart_node(chart_graph))
    graph.add_node(CHAT, _chat_node)

    graph.add_edge(START, ORCHESTRATOR)
    graph.add_conditional_edges(ORCHESTRATOR, route_after_orchestrator)
    graph.add_edge(QUERY_SUBGRAPH, END)
    graph.add_edge(INSIGHT_SUBGRAPH, END)
    graph.add_edge(CHART_SUBGRAPH, END)
    graph.add_edge(CHAT, END)

    return graph.compile(checkpointer=checkpointer)
