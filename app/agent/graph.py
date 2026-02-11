from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from app.agent.nodes.executor import Executor
from app.agent.nodes.follow_up import FollowUp
from app.agent.nodes.intent_parse import IntentParse
from app.agent.nodes.schema_retriever import SchemaRetriever
from app.agent.nodes.sql_generator import SQLGenerator
from app.agent.nodes.sql_validator import SQLValidator
from app.agent.states import NL2SQLState
from app.core.config import settings

# 节点名称常量
SCHEMA_RETRIEVER = "schema_retriever"
INTENT_PARSE = "intent_parse"
FOLLOW_UP = "follow_up"
SQL_GENERATOR = "sql_generator"
SQL_VALIDATOR = "sql_validator"
EXECUTOR = "executor"


def route_after_intent_parse(state: NL2SQLState) -> str:
    """意图解析后的路由：追问 / 重新检索 / 生成 SQL"""
    result = state.intent_parse_result
    if result.need_follow_up:
        return FOLLOW_UP
    if result.need_retry_retrieve:
        return SCHEMA_RETRIEVER
    return SQL_GENERATOR


def route_after_validate(state: NL2SQLState) -> str:
    """SQL 校验后的路由：超过重试上限终止 / 语法错误 / 表字段错误 / 性能问题 / 通过"""
    if state.retry_count >= settings.AGENT_MAX_RETRIES:
        return END
    if state.syntax_result and not state.syntax_result.is_ok:
        return SQL_GENERATOR
    if state.explain_error:
        return SCHEMA_RETRIEVER
    if state.performance_result and not state.performance_result.is_ok:
        return INTENT_PARSE
    return EXECUTOR


def _build_graph():
    graph = StateGraph(NL2SQLState)

    graph.add_node(SCHEMA_RETRIEVER, SchemaRetriever())
    graph.add_node(INTENT_PARSE, IntentParse())
    graph.add_node(FOLLOW_UP, FollowUp())
    graph.add_node(SQL_GENERATOR, SQLGenerator())
    graph.add_node(SQL_VALIDATOR, SQLValidator())
    graph.add_node(EXECUTOR, Executor())

    graph.add_edge(START, SCHEMA_RETRIEVER)
    graph.add_edge(SCHEMA_RETRIEVER, INTENT_PARSE)
    graph.add_conditional_edges(INTENT_PARSE, route_after_intent_parse)
    graph.add_edge(FOLLOW_UP, INTENT_PARSE)
    graph.add_edge(SQL_GENERATOR, SQL_VALIDATOR)
    graph.add_conditional_edges(SQL_VALIDATOR, route_after_validate)
    graph.add_edge(EXECUTOR, END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_graph():
    return _build_graph()
