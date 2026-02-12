from typing import List

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.vars.prompts import (
    INTENT_RECOGNITION_SYSTEM_PROMPT,
    INTENT_RECOGNITION_HUMAN_PROMPT,
    GENERATE_SQL_SYSTEM_PROMPT,
    GENERATE_SQL_HUMAN_PROMPT,
    RESULT_SUMMARY_SYSTEM_PROMPT,
    RESULT_SUMMARY_HUMAN_PROMPT,
    SQL_JUDGE_SYSTEM_PROMPT,
    SQL_JUDGE_HUMAN_PROMPT,
)
from app.vars.vars import HUMAN_TYPE, SYSTEM_TYPE


class ChatPrompt:

    @classmethod
    def intent_recognition_prompt(cls, **kwargs) -> List[BaseMessage]:
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, INTENT_RECOGNITION_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            (HUMAN_TYPE, INTENT_RECOGNITION_HUMAN_PROMPT),
        ])
        return template.format_messages(**kwargs)

    @classmethod
    def generate_sql_prompt(cls, **kwargs) -> List[BaseMessage]:
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, GENERATE_SQL_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            (HUMAN_TYPE, GENERATE_SQL_HUMAN_PROMPT),
        ])
        return template.format_messages(**kwargs)

    @classmethod
    def result_summary_prompt(cls, **kwargs) -> List[BaseMessage]:
        """构建结果总结 prompt：对话历史 + SQL + 执行结果"""
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, RESULT_SUMMARY_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            (HUMAN_TYPE, RESULT_SUMMARY_HUMAN_PROMPT),
        ])
        return template.format_messages(**kwargs)

    @classmethod
    def judge_prompt(cls, **kwargs) -> List[BaseMessage]:
        template = ChatPromptTemplate.from_messages([
            (SYSTEM_TYPE, SQL_JUDGE_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            (HUMAN_TYPE, SQL_JUDGE_HUMAN_PROMPT),
        ])
        return template.format_messages(**kwargs)
