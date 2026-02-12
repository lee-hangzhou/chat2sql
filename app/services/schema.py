import asyncio
from typing import Any

from pymilvus import DataType

from app.core.config import settings
from app.core.database import BusinessDatabase, business_db
from app.core.logger import logger
from app.core.retrieval_client import RetrievalClient, retrieval_client

_NULLABLE_YES = "YES"
_COLUMN_KEY_PRI = "PRI"
_COLUMN_KEY_UNI = "UNI"

_SCHEMA_QUERY = """
SELECT
    c.TABLE_NAME,
    t.TABLE_COMMENT,
    c.COLUMN_NAME,
    c.COLUMN_TYPE,
    c.COLUMN_COMMENT,
    c.IS_NULLABLE,
    c.COLUMN_KEY
FROM information_schema.COLUMNS c
JOIN information_schema.TABLES t
    ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
WHERE c.TABLE_SCHEMA = DATABASE()
    AND t.TABLE_TYPE = 'BASE TABLE'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
"""


class SchemaService:
    """从业务数据库读取表结构并同步到 Milvus 向量库"""

    def __init__(
        self,
        db: BusinessDatabase = business_db,
        retriever: RetrievalClient = retrieval_client,
    ) -> None:
        self.db = db
        self.retriever = retriever

    async def sync(self) -> int:
        """全量同步：清空 collection 后重建。返回同步的表数量。"""
        table_schemas = await self._read_table_schemas()
        if not table_schemas:
            logger.warning("schema_sync.no_tables")
            return 0

        texts = [s["text"] for s in table_schemas]
        embeddings = await asyncio.to_thread(
            self.retriever.sentence_transformer.encode, texts
        )

        collection_name = settings.MILVUS_COLLECTION_NAME
        dim = embeddings.shape[1]

        self._recreate_collection(collection_name, dim)

        data = [
            {
                settings.MILVUS_SCHEMA_FIELD: schema["text"],
                "embedding": emb.tolist(),
            }
            for schema, emb in zip(table_schemas, embeddings)
        ]
        self.retriever.insert(collection_name, data)

        logger.info("schema_sync.completed", table_count=len(table_schemas))
        return len(table_schemas)

    async def _read_table_schemas(self) -> list[dict[str, str]]:
        """从业务数据库读取所有表结构，按表分组并格式化为文本"""
        conn = self.db.get_connection()
        _, rows = await conn.execute_query(_SCHEMA_QUERY)

        tables: dict[str, dict[str, Any]] = {}
        for row in rows:
            table_name = row["TABLE_NAME"]
            if table_name not in tables:
                tables[table_name] = {
                    "name": table_name,
                    "comment": row["TABLE_COMMENT"] or "",
                    "columns": [],
                }
            tables[table_name]["columns"].append({
                "name": row["COLUMN_NAME"],
                "type": row["COLUMN_TYPE"],
                "comment": row["COLUMN_COMMENT"] or "",
                "nullable": row["IS_NULLABLE"] == _NULLABLE_YES,
                "key": row["COLUMN_KEY"],
            })

        return [{"text": self._format_table(t)} for t in tables.values()]

    @staticmethod
    def _format_table(table: dict[str, Any]) -> str:
        """将表结构格式化为 LLM 友好的文本"""
        header = f"Table: {table['name']}"
        if table["comment"]:
            header += f" ({table['comment']})"

        lines = [header, "Columns:"]
        for col in table["columns"]:
            parts = [f"  - {col['name']} ({col['type']})"]
            if col["key"] == _COLUMN_KEY_PRI:
                parts.append("PK")
            elif col["key"] == _COLUMN_KEY_UNI:
                parts.append("UNIQUE")
            if not col["nullable"]:
                parts.append("NOT NULL")
            if col["comment"]:
                parts.append(col["comment"])
            lines.append(", ".join(parts))

        return "\n".join(lines)

    def _recreate_collection(self, name: str, dim: int) -> None:
        """清空并重建 Milvus collection"""
        if self.retriever.has_collection(name):
            self.retriever.drop_collection(name)

        schema = self.retriever.create_schema(auto_id=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field(
            settings.MILVUS_SCHEMA_FIELD, DataType.VARCHAR, max_length=65535
        )
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)

        index_params = self.retriever.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 256},
        )

        self.retriever.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params,
        )
