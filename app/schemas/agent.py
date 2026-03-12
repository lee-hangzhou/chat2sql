from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.dialect import ExplainAnalysis


class DatabaseType(str, Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    CLICKHOUSE = "clickhouse"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"
    HORIZONTAL_BAR = "horizontal_bar"
    FUNNEL = "funnel"
    NONE = "none"


class OrchestratorIntent(str, Enum):
    """Orchestrator 主图的意图分类"""
    QUERY = "query"
    INSIGHT = "insight"
    CHART_UPDATE = "chart_update"
    CHAT = "chat"


class OrchestratorIntentResult(BaseModel):
    """LLM 意图分类输出"""
    intent: OrchestratorIntent = Field(description="用户意图分类")


class AgentErrorCode(str, Enum):
    """Agent 错误码"""

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
    is_query_intent: bool = Field(default=True, description="用户输入是否为数据查询意图")
    is_presentation_change: bool = Field(default=False, description="用户请求是否仅涉及图表/展示变更，无需重新查询数据")
    direct_reply: Optional[str] = Field(default=None, description="非查询意图时的直接回复")
    need_follow_up: Optional[bool] = Field(default=None, description="是否需要追问")
    follow_up_question: Optional[str] = Field(default=None, description="追问的问题")
    wants_chart: Optional[bool] = Field(default=None, description="用户是否明确要求可视化")
    chart_preference: Optional[ChartType] = Field(default=None, description="用户指定的图表类型，未指定则由系统推荐")


class ChartAdvice(BaseModel):
    """LLM 输出的图表建议，仅包含类型和字段映射"""
    chart_type: ChartType = Field(description="推荐的图表类型")
    title: str = Field(description="图表标题")
    x_field: Optional[str] = Field(default=None, description="X 轴对应的列名")
    y_field: Optional[str] = Field(default=None, description="Y 轴对应的列名")
    series_field: Optional[str] = Field(default=None, description="分组/系列对应的列名")


class SQLResult(BaseModel):
    sql: Optional[str] = Field(default=None, description="生成的SQL语句")


class JudgeResult(BaseModel):
    choice: int = Field(..., description="被选中候选的序号，从 1 开始")


class SyntaxResult(BaseModel):
    is_ok: bool = Field(..., description="语法校验是否通过")
    error: str = Field(default=None, description="语法校验存在的问题列表")


class PerformanceResult(BaseModel):
    is_ok: bool = Field(..., description="性能校验是否通过")
    issues: List[str] = Field(default_factory=list, description="性能问题列表")
    explains: Optional[str] = Field(default=None, description="原始 EXPLAIN 执行计划")


class ValidatedCandidate(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    explain: ExplainAnalysis = Field(..., description="EXPLAIN 分析结果")


class CandidateExecResult(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    explain: ExplainAnalysis = Field(..., description="EXPLAIN 分析结果")
    exec_result: List[Dict[str, Any]] = Field(default_factory=list, description="执行结果样本")
