from typing import Any, Annotated, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

from app.schemas.agent import IntentParseResult, PerformanceResult, SQLResult, SyntaxResult


def merge_schemas(existing: List[str], new: List[str]) -> List[str]:
    return list(dict.fromkeys(existing + new))


class NL2SQLState(BaseModel):
    """
    NL2SQL全局状态，记录用户输入、意图解析、SQL生成及执行情况
    """
    schemas: Annotated[List[str], merge_schemas] = Field(default_factory=list, description="检索的表结构列表")
    intent_parse_result: Optional[IntentParseResult] = Field(default=None, description="格式化的意图解析")
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list, description="对话消息记录")
    sql_result: Optional[SQLResult] = Field(default=None, description="生成的SQL语句")

    # 重试计数（由 sql_validator 节点在校验失败时递增）
    retry_count: int = Field(default=0, description="SQL 校验失败重试次数")

    # SQL 校验结果（由 sql_validator 节点写入）
    syntax_result: Optional[SyntaxResult] = Field(default=None, description="SQL语法校验结果")
    explain_error: Optional[str] = Field(default=None, description="EXPLAIN执行SQL层面错误信息")
    performance_result: Optional[PerformanceResult] = Field(default=None, description="SQL性能校验结果")

    # SQL 执行结果（由 executor 节点写入）
    execute_result: Optional[List[Dict[str, Any]]] = Field(default=None, description="SQL执行结果集")
