from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
from app.core import Singleton, settings


class RetrievalClient(MilvusClient, Singleton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sentence_transformer = SentenceTransformer(
            settings.EMBEDDING_MODEL,
        )



retrieval_client = RetrievalClient(uri=settings.MILVUS_URI)
