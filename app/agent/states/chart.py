from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class ChartState(BaseModel):
    chart_option: Optional[Dict[str, Any]] = Field(default=None, description="ECharts option JSON")
    chart_message: Optional[str] = Field(default=None, description="图表生成失败时的原因说明，由 result_summarizer 纳入总结")
