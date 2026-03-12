from app.core.vector_store import vector_store_manager


class SchemaRetriever:
    def __init__(self):
        self._vs_manager = vector_store_manager

    @staticmethod
    def _build_retrieval_query():

        pass