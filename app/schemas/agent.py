from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ast import QueryElement


class DatabaseType(Enum):
    MySQL = "mysql"


class IntentParseResult(BaseModel):
    need_flow_up: Optional[bool] = Field(default=None, description="是否需要追问")
    need_retry_retrieve: Optional[bool] = Field(default=None, description="是否需要重新检索schema")
    ir_ast: Optional[QueryElement] = Field(default=None, description="中间表示的抽象语法树")
    flow_up_question: Optional[str] = Field(default=None, description="追问的问题")


class SQLResult(BaseModel):
    sql: Optional[str] = Field(default=None, description="生成的SQL语句")


class SyntaxResult(BaseModel):
    is_ok: bool = Field(..., description="语法校验是否通过")
    error: str = Field(default=None, description="语法校验存在的问题列表")

class Explain(BaseModel):
    """MySQL EXPLAIN 执行计划单行结果"""
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[int] = Field(default=None, description="SELECT 标识符")
    select_type: Optional[str] = Field(default=None, description="SELECT 类型，如 SIMPLE、PRIMARY、SUBQUERY 等")
    table: Optional[str] = Field(default=None, description="访问的表名")
    partitions: Optional[str] = Field(default=None, description="匹配的分区")
    join_type: Optional[str] = Field(default=None, alias="type", description="连接类型，如 ALL、index、range、ref、const 等")
    possible_keys: Optional[str] = Field(default=None, description="可能使用的索引")
    key: Optional[str] = Field(default=None, description="实际使用的索引")
    key_len: Optional[str] = Field(default=None, description="使用的索引长度")
    ref: Optional[str] = Field(default=None, description="与索引比较的列或常量")
    rows: int = Field(default=0, description="预估扫描行数")
    filtered: Optional[float] = Field(default=None, description="按条件过滤后的行百分比")
    extra: str = Field(default="", description="额外信息，如 Using where、Using index 等")

class PerformanceResult(BaseModel):
    is_ok: bool = Field(..., description="性能校验是否通过")
    issues: List[str] = Field(default_factory=list, description="性能问题列表")
    explains: Optional[str] = Field(default=None, description="原始 EXPLAIN 执行计划")


class ExecuteExplainResult(BaseModel):
    error:Optional[str] = Field(default=None,description="执行explain错误信息")
    explains:List[Explain] = Field(default_factory=list,description="执行explain的结果")
