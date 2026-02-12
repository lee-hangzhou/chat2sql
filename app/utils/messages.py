from typing import List

from langchain_core.messages import BaseMessage

from app.core.config import settings


def trim_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
    """保留首条用户消息 + 最近 N 轮，防止 prompt 无限膨胀"""
    max_count = settings.AGENT_MAX_MESSAGE_PAIRS * 2 + 1
    if len(messages) <= max_count:
        return messages
    return [messages[0]] + messages[-(max_count - 1):]
