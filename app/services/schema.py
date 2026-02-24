import asyncio
import hashlib

from langchain_classic.indexes import SQLRecordManager
from langchain_core.documents import Document
from langchain_core.indexing.api import index as langchain_index

from app.core.database import business_db
from app.core.logger import logger
from app.core.vector_store import vector_store_manager


class SchemaService:
    """从业务数据库读取表结构并同步到 Milvus 向量库"""
    _SOURCE_ID_KEY = "table"
    _RECORD_MANAGER_DB = "sqlite:///./schema_record_manager.db"
    _RECORD_MANAGER_NAMESPACE = "schema_sync"

    def __init__(self) -> None:
        self._record_manager = SQLRecordManager(
            namespace=self._RECORD_MANAGER_NAMESPACE,
            db_url=self._RECORD_MANAGER_DB,
        )
        self._record_manager.create_schema()

    async def sync(self) -> int:
        """读取业务库表结构，增量同步到 Milvus，返回同步的表数量"""
        docs = await self._read_schemas()
        if not docs:
            logger.warning("schema_sync.no_tables")
            return 0

        vector_store = vector_store_manager.vector_store
        result = await asyncio.to_thread(
            langchain_index,
            docs,
            self._record_manager,
            vector_store,
            cleanup="full",  # type:ignore
            source_id_key=self._SOURCE_ID_KEY,
            key_encoder=lambda content: hashlib.sha256(content.encode()).hexdigest(),  # type:ignore
        )

        logger.info(
            "schema_sync.completed",
            num_added=result.get("num_added", 0),
            num_updated=result.get("num_updated", 0),
            num_deleted=result.get("num_deleted", 0),
            num_skipped=result.get("num_skipped", 0),
        )
        return result.get("num_added", 0) + result.get("num_updated", 0)

    async def _read_schemas(self) -> list[Document]:
        """通过 SQLAlchemy metadata 反射读取所有表的 DDL，每张表一个 Document"""
        ddls = await business_db.get_table_ddls()
        return [
            Document(
                page_content=ddl.strip(),
                metadata={self._SOURCE_ID_KEY: table_name},
            )
            for table_name, ddl in ddls
            if ddl and ddl.strip()
        ]

    @staticmethod
    async def has_schemas() -> bool:
        """检查 Milvus collection 中是否已有数据"""
        try:
            vs = vector_store_manager.vector_store
            col = vs.col
            if col is None:
                return False
            return col.num_entities > 0
        except Exception as e:
            logger.info("SchemaService.has_schemas:milvus has no schemas", e)
            return False
