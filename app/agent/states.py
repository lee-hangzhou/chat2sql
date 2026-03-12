from typing import Any, Annotated, Dict, List, Literal, Optional

from langchain_core.messages import AnyMessage, BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

from app.schemas.agent import (
    AgentErrorCode, CandidateExecResult, IntentParseResult,
    OrchestratorIntent, PerformanceResult, SQLResult, SyntaxResult, ValidatedCandidate,
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
    summarized_messages: List[AnyMessage] = Field(default_factory=list, description="摘要后的消息列表，由 SummarizationNode 写入，LLM 节点从此读取")
    context: Dict[str, Any] = Field(default_factory=dict, description="SummarizationNode 运行时上下文，存储 RunningSummary")
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

    # 图表（由 chart_advisor 节点写入）
    chart_option: Optional[Dict[str, Any]] = Field(default=None, description="ECharts option JSON")
    chart_message: Optional[str] = Field(default=None, description="图表生成失败时的原因说明，由 result_summarizer 纳入总结")

    # 终态（由 sql_validator / executor 写入）
    is_success: Optional[bool] = Field(default=None, description="最终执行是否成功")
    error_code: Optional[AgentErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败时的错误描述")


class OrchestratorState(BaseModel):
    """
    主 Orchestrator 图状态，只含路由信息和最终输出，不含子图内部过程字段
    """
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list, description="对话历史")
    current_intent: Optional[OrchestratorIntent] = Field(default=None, description="当前轮次意图")
    cached_query_result: Optional[List[Dict[str, Any]]] = Field(default=None, description="跨轮缓存的查询结果集，避免重复执行 SQL")
    chart_option: Optional[Dict[str, Any]] = Field(default=None, description="当前图表配置")
    query_output: Optional[List[Dict[str, Any]]] = Field(default=None, description="最新一轮查询结果")
    insight_report: Optional[dict] = Field(default=None, description="Insight 子图输出")
    final_response: Optional[str] = Field(default=None, description="最终文本回复")
    is_success: Optional[bool] = Field(default=None, description="本轮是否成功")
    error_code: Optional[AgentErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败时的错误描述")


class InsightFinding(BaseModel):
    """
    单条洞察结论数据模型
    """
    conclusion: str = Field(description="洞察结论")
    data_slice: Dict[str, Any] = Field(description="支撑数据切片")
    chart_suggestion: Optional[str] = Field(default=None, description="建议的 ECharts 图表类型")
    severity: Literal["high", "medium", "low"] = Field(description="洞察重要程度，取值为 high / medium / low")


class InsightState(BaseModel):
    """
    Insight 子图内部状态
    """
    query_output: List[Dict[str, Any]] = Field(default_factory=list, description="输入数据，从 OrchestratorState 传入")
    user_question: str = Field(default="", description="用户原始问题")
    analysis_plan: List[str] = Field(default_factory=list, description="InsightPlanner 制定的分析维度列表")
    supplemental_queries: List[str] = Field(default_factory=list, description="DataFetcher 需要补充的查询列表")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="AnomalyDetector 发现的异常点")
    hypotheses: List[str] = Field(default_factory=list, description="HypothesisGenerator 生成的假设")
    validated_hypotheses: List[str] = Field(default_factory=list, description="验证通过的假设")
    findings: List[InsightFinding] = Field(default_factory=list, description="最终洞察结论列表")
    insight_summary: Optional[str] = Field(default=None, description="InsightSummarizer 生成的报告文本")
    hypothesis_retry_count: int = Field(default=0, description="假设验证重试次数")
    is_success: Optional[bool] = Field(default=None, description="子图是否成功")
    error_code: Optional[AgentErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败时的错误描述")
