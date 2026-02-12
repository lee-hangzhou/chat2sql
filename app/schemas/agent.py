from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatabaseType(str, Enum):
    MYSQL = "mysql"


class AgentErrorCode(str, Enum):
    """Agent 错误码，每个成员携带 code（用于调用方逻辑判断）和 message（默认描述）"""

    def __new__(cls, code: str, message: str):
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.message = message
        return obj

    EMPTY_QUERY = ("empty_query", "无法从对话历史中提取有效的用户查询")
    NO_SCHEMA_RESULTS = ("no_schema_results", "未检索到匹配的表结构")
    SCHEMA_RETRY_LIMIT = ("schema_retry_limit", "Schema 检索次数已达上限")
    FOLLOW_UP_LIMIT = ("follow_up_limit", "追问次数已达上限")
    NO_SQL = ("no_sql", "SQL 结果为空")
    ONLY_SELECT = ("only_select", "仅允许 SELECT 语句")
    LLM_ERROR = ("llm_error", "LLM 调用失败")
    RETRIEVAL_ERROR = ("retrieval_error", "向量检索失败")
    EXECUTION_ERROR = ("execution_error", "SQL 执行失败")
    VALIDATION_RETRY_LIMIT = ("validation_retry_limit", "SQL 校验重试次数已达上限")
    VALIDATION_ALL_FAILED = ("validation_all_failed", "所有候选均校验失败")


class IntentParseResult(BaseModel):
    need_follow_up: Optional[bool] = Field(default=None, description="是否需要追问")
    need_retry_retrieve: Optional[bool] = Field(default=None, description="是否需要重新检索schema")
    follow_up_question: Optional[str] = Field(default=None, description="追问的问题")


class SQLResult(BaseModel):
    sql: Optional[str] = Field(default=None, description="生成的SQL语句")


class JudgeResult(BaseModel):
    choice: int = Field(..., description="被选中候选的序号（从 1 开始）")


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
    error: Optional[str] = Field(default=None, description="执行explain错误信息")
    explains: List[Explain] = Field(default_factory=list, description="执行explain的结果")


class ValidatedCandidate(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    explains: List[Explain] = Field(default_factory=list, description="EXPLAIN 执行计划")


class CandidateExecResult(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    explains: List[Explain] = Field(default_factory=list, description="EXPLAIN 执行计划")
    exec_result: List[Dict[str, Any]] = Field(default_factory=list, description="执行结果样本")
