import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agent.prompts import ChatPrompt
from app.agent.states import NL2SQLState
from app.core.config import settings
from app.core.llm import llm
from app.core.logger import logger
from app.utils.messages import trim_messages
from app.utils.timing import log_elapsed


class ResultSummarizer:
    """调用 LLM 对查询结果进行自然语言总结"""

    _SAMPLE_MAX_ROWS = 20
    _EMPTY_RESULT_TEXT = "(无数据)"
    _FALLBACK_NO_DATA = "查询完成，未找到匹配的数据。"
    _FALLBACK_WITH_DATA = "查询完成，共返回 {} 行数据。"

    def __init__(self):
        self.llm = llm.with_retry(
            stop_after_attempt=settings.LLM_RETRY_ATTEMPTS,
            wait_exponential_jitter=True,
        )

    def _build_result_sample(self, rows: List[Dict[str, Any]]) -> str:
        """将执行结果截取后序列化为文本，供 prompt 使用"""
        if not rows:
            return self._EMPTY_RESULT_TEXT
        sample = rows[:self._SAMPLE_MAX_ROWS]
        return json.dumps(sample, ensure_ascii=False, default=str)

    async def __call__(self, state: NL2SQLState) -> Dict[str, Any]:
        """根据用户问题、SQL 和执行结果生成自然语言总结，写入 messages"""
        sql = state.sql_result.sql if state.sql_result else ""
        rows = state.execute_result or []

        prompt_messages = ChatPrompt.result_summary_prompt(
            messages=trim_messages(state.messages),
            sql=sql,
            row_count=len(rows),
            result_sample=self._build_result_sample(rows),
        )

        try:
            async with log_elapsed(logger, "result_summarizer.completed"):
                response = await self.llm.ainvoke(prompt_messages)
            summary = response.content.strip()
        except Exception as e:
            logger.warning("result_summarizer.failed", error=str(e))
            summary = self._fallback_summary(len(rows))

        content = f"```sql\n{sql}\n```\n\n{summary}" if sql else summary
        return {"messages": [AIMessage(content=content)]}

    @classmethod
    def _fallback_summary(cls, row_count: int) -> str:
        """LLM 调用失败时的兜底文案"""
        if row_count == 0:
            return cls._FALLBACK_NO_DATA
        return cls._FALLBACK_WITH_DATA.format(row_count)
