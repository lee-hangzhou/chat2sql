from typing import Any, Annotated, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

from app.schemas.agent import (
    AgentErrorCode, CandidateExecResult, IntentParseResult,
    PerformanceResult, SQLResult, SyntaxResult, ValidatedCandidate,
)


def merge_schemas(existing: List[str], new: List[str]) -> List[str]:
    return list(dict.fromkeys(existing + new))


class NL2SQLState(BaseModel):
    """
    NL2SQL全局状态，记录用户输入、意图解析、SQL生成及执行情况
    """
    user_id: Optional[str] = Field(default=None, description="用户标识，由调用方注入，用于审计")
    schemas: Annotated[List[str], merge_schemas] = Field(default_factory=list, description="检索的表结构列表")
    intent_parse_result: Optional[IntentParseResult] = Field(default=None, description="格式化的意图解析")
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list, description="对话消息记录")
    sql_candidates: List[SQLResult] = Field(default_factory=list, description="SQL 候选列表，由 sql_generator 生成")
    validated_candidates: List[ValidatedCandidate] = Field(default_factory=list, description="通过校验的候选，由 sql_validator 写入")
    candidate_exec_results: List[CandidateExecResult] = Field(default_factory=list, description="已执行候选的比对结果，由 sql_selector 写入")
    sql_result: Optional[SQLResult] = Field(default=None, description="选优后的最终 SQL")
    needs_arbitration: bool = Field(default=False, description="结果不一致，需要仲裁")

    # 循环计数
    retry_count: int = Field(default=0, description="SQL 校验失败重试次数")
    schema_retry_count: int = Field(default=0, description="Schema 检索次数")
    follow_up_count: int = Field(default=0, description="追问次数")

    # SQL 校验结果（由 sql_validator 节点写入）
    syntax_result: Optional[SyntaxResult] = Field(default=None, description="SQL语法校验结果")
    explain_error: Optional[str] = Field(default=None, description="EXPLAIN执行SQL层面错误信息")
    performance_result: Optional[PerformanceResult] = Field(default=None, description="SQL性能校验结果")

    # SQL 执行结果（由 executor 节点写入）
    execute_result: Optional[List[Dict[str, Any]]] = Field(default=None, description="SQL执行结果集")

    # 终态（由 sql_validator / executor 写入）
    is_success: Optional[bool] = Field(default=None, description="最终执行是否成功")
    error_code: Optional[AgentErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败时的错误描述")
