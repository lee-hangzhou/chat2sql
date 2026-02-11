from typing import Any

from langchain_ollama import ChatOllama

from app.core import Singleton


class ChatClient(ChatOllama, Singleton):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        pass






llm = ChatClient(
    model="",
    base_url="",
    timeout=60,
)

llm.with_structured_output()