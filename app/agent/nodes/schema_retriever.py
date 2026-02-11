from typing import Dict

from app.agent.states import NL2SQLState
from app.core.retrieval_client import retrieval_client
from app.vars.vars import HUMAN_TYPE


class SchemaRetriever:
    def __init__(self):
        self.retriever = retrieval_client

    @staticmethod
    def _build_retrieval_query(state: NL2SQLState) -> str:
        """
        从对话历史中提取用户消息构建检索查询
        - 只保留 HumanMessage
        - 按时间顺序拼接，让向量模型理解查询演进
        """
        if not state.messages:
            return ""

        user_messages = [
            msg.content for msg in state.messages
            if msg.type == HUMAN_TYPE
        ]

        return "\n".join(user_messages)

    def _search(self, state: NL2SQLState) -> Dict[str, any]:
        """
        根据用户输入检索相似度最高的5张表
        """
        message = self._build_retrieval_query(state)
        embedding = self.retriever.sentence_transformer.encode(message)
        search_params = {
            "metric_type": "COSINE",
            "params": {
                "ef": 64
            }
        }
        results = self.retriever.search(
            "collection_name",  # todo 集合名在创建时定义
            data=[embedding],
            limit=5,
            search_params=search_params,
            output_fields=["table_schema"]  # todo 标量字段，应在创建集合时定义
        )
        if len(results) == 0:
            raise  # todo 是否要加这个判断

        schemas = list()
        for hit in results[0]:
            schemas.append(hit["entity"]["table_schema"])

        return {"schemas": schemas}

    def __call__(self, state: NL2SQLState) -> Dict[str, any]:
        return self._search(state)
