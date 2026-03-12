from langmem.short_term import SummarizationNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.chart_advisor import ChartAdvisor
from app.agent.nodes.executor import Executor
from app.agent.nodes.follow_up import FollowUp
from app.agent.nodes.intent_parse import IntentParse
from app.agent.nodes.result_summarizer import ResultSummarizer
from app.agent.nodes.schema_retriever import SchemaRetriever
from app.agent.nodes.sql_generator import SQLGenerator
from app.agent.nodes.sql_judge import SQLJudge
from app.agent.nodes.sql_selector import SQLSelector
from app.agent.nodes.sql_validator import SQLValidator
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm

SUMMARIZE = "summarize"
SCHEMA_RETRIEVER = "schema_retriever"
INTENT_PARSE = "intent_parse"
FOLLOW_UP = "follow_up"
SQL_GENERATOR = "sql_generator"
SQL_VALIDATOR = "sql_validator"
SQL_SELECTOR = "sql_selector"
SQL_JUDGE = "sql_judge"
EXECUTOR = "executor"
CHART_ADVISOR = "chart_advisor"
RESULT_SUMMARIZER = "result_summarizer"


def route_after_intent_parse(state: NL2SQLState) -> str:
    """展示变更 → CHART_ADVISOR，非查询 → END，追问 → FOLLOW_UP，查询意图 → SCHEMA_RETRIEVER"""
    if state.is_success is False:
        return END
    result = state.intent_parse_result
    if result.is_presentation_change:
        return CHART_ADVISOR
    if not result.is_query_intent:
        return END
    if result.need_follow_up:
        return FOLLOW_UP
    return SCHEMA_RETRIEVER


def route_after_schema_retriever(state: NL2SQLState) -> str:
    if state.is_success is False:
        return END
    return SQL_GENERATOR


def route_after_follow_up(state: NL2SQLState) -> str:
    if state.is_success is False:
        return END
    return SUMMARIZE


def route_after_sql_generator(state: NL2SQLState) -> str:
    if state.is_success is False:
        return END
    return SQL_VALIDATOR


def route_after_validate(state: NL2SQLState) -> str:
    """校验后路由：有合法候选 → 选优；仲裁候选失败但有历史结果 → 裁决；否则重试"""
    if state.is_success is False:
        return END
    if state.validated_candidates:
        return SQL_SELECTOR
    if state.candidate_exec_results:
        return SQL_JUDGE
    if state.retry_count >= settings.AGENT_MAX_RETRIES:
        return END
    if state.syntax_result and not state.syntax_result.is_ok:
        return SQL_GENERATOR
    if state.explain_error:
        return SCHEMA_RETRIEVER
    return END


def route_after_selector(state: NL2SQLState) -> str:
    """选优后路由：仲裁 → 生成；有结果 → 执行；无结果 → 裁决"""
    if state.needs_arbitration:
        return SQL_GENERATOR
    if state.sql_result:
        return EXECUTOR
    return SQL_JUDGE


def route_after_judge(state: NL2SQLState) -> str:
    if state.is_success is False:
        return END
    return EXECUTOR


def route_after_executor(state: NL2SQLState) -> str:
    if state.is_success is False:
        return END
    return CHART_ADVISOR


def build_query_graph(checkpointer=None) -> CompiledStateGraph:
    """构建 NL2SQL query 子图，checkpointer 由调用方注入"""
    graph = StateGraph(NL2SQLState)

    summarization_node = SummarizationNode(
        model=llm.bind(max_tokens=settings.SUMMARIZATION_MAX_SUMMARY_TOKENS),
        max_tokens=settings.SUMMARIZATION_MAX_TOKENS,
        max_summary_tokens=settings.SUMMARIZATION_MAX_SUMMARY_TOKENS,
    )

    graph.add_node(SUMMARIZE, summarization_node)
    graph.add_node(SCHEMA_RETRIEVER, SchemaRetriever())
    graph.add_node(INTENT_PARSE, IntentParse())
    graph.add_node(FOLLOW_UP, FollowUp())
    graph.add_node(SQL_GENERATOR, SQLGenerator())
    graph.add_node(SQL_VALIDATOR, SQLValidator())
    graph.add_node(SQL_SELECTOR, SQLSelector())
    graph.add_node(SQL_JUDGE, SQLJudge())
    graph.add_node(EXECUTOR, Executor())
    graph.add_node(CHART_ADVISOR, ChartAdvisor())
    graph.add_node(RESULT_SUMMARIZER, ResultSummarizer())

    graph.add_edge(START, SUMMARIZE)
    graph.add_edge(SUMMARIZE, INTENT_PARSE)
    graph.add_conditional_edges(INTENT_PARSE, route_after_intent_parse)
    graph.add_conditional_edges(SCHEMA_RETRIEVER, route_after_schema_retriever)
    graph.add_conditional_edges(FOLLOW_UP, route_after_follow_up)
    graph.add_conditional_edges(SQL_GENERATOR, route_after_sql_generator)
    graph.add_conditional_edges(SQL_VALIDATOR, route_after_validate)
    graph.add_conditional_edges(SQL_SELECTOR, route_after_selector)
    graph.add_conditional_edges(SQL_JUDGE, route_after_judge)
    graph.add_conditional_edges(EXECUTOR, route_after_executor)
    graph.add_edge(CHART_ADVISOR, RESULT_SUMMARIZER)
    graph.add_edge(RESULT_SUMMARIZER, END)

    return graph.compile(checkpointer=checkpointer)
