from typing import Dict, Any, Optional, Literal, List

from pydantic import BaseModel, Field


class InsightFinding(BaseModel):
    """
    单条洞察结论数据模型
    """
    conclusion: str = Field(description="洞察结论")
    data_slice: Dict[str, Any] = Field(description="支撑数据切片")
    chart_suggestion: Optional[str] = Field(default=None, description="建议的 ECharts 图表类型")
    severity: Literal["high", "medium", "low"] = Field(description="洞察重要程度，取值为 high / medium / low") # todo 需要改为枚举


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
