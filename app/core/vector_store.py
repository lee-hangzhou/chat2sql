from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_milvus import Milvus

from app.core.config import settings
from app.core.singleton import Singleton


class VectorStoreManager(Singleton):
    """管理 HuggingFaceEmbeddings 和 Milvus VectorStore 的生命周期"""

    def __init__(self) -> None:
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._vector_store: Optional[Milvus] = None

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL
            )
        return self._embeddings

    @property
    def vector_store(self) -> Milvus:
        if self._vector_store is None:
            self._vector_store = Milvus(
                embedding_function=self.embeddings,
                connection_args={"uri": settings.MILVUS_URI},
                collection_name=settings.MILVUS_COLLECTION_NAME,
                auto_id=True,
            )
        return self._vector_store


vector_store_manager = VectorStoreManager()
