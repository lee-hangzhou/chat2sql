from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.schema import CreateTable
from tortoise import Tortoise

from app.core.config import settings
from app.core.logger import logger
from app.core.singleton import Singleton


class Database(Singleton):
    _MIN_SIZE: int = 5
    _MAX_SIZE: int = 20
    _CONNECT_TIMEOUT: int = 10
    _POOL_RECYCLE: int = 3600

    def __init__(self) -> None:
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _add_pool_params(self, base_url: str) -> str:
        """Add connection pool parameters to database URL."""
        if base_url.startswith("sqlite"):
            return base_url

        parsed = urlparse(base_url)
        params = parse_qs(parsed.query)

        pool_config = {
            "minsize": self._MIN_SIZE,
            "maxsize": self._MAX_SIZE,
            "connect_timeout": self._CONNECT_TIMEOUT,
            "pool_recycle": self._POOL_RECYCLE,
        }

        for key, value in pool_config.items():
            if key not in params:
                params[key] = [str(value)]

        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))  # type:ignore

    async def connect(self, db_url: Optional[str] = None) -> None:
        if self._initialized:
            logger.warning("Database already initialized")
            return

        url = db_url or settings.DATABASE_URL
        full_url = self._add_pool_params(url)

        tortoise_config = {
            "connections": {"default": full_url},
            "apps": {
                "models": {
                    "models": ["app.models"],
                    "default_connection": "default",
                }
            },
            "use_tz": True,
        }

        await Tortoise.init(
            config=tortoise_config,
            _enable_global_fallback=True,
        )
        await Tortoise.generate_schemas(safe=True)

        self._initialized = True
        logger.info("Database initialized")

    async def disconnect(self) -> None:
        if not self._initialized:
            return

        await Tortoise.close_connections()
        self._initialized = False
        logger.info("Database connections closed")


db = Database()


class BusinessDatabase(Singleton):
    """业务数据库连接"""

    _POOL_SIZE = 5
    _MAX_OVERFLOW = 15
    _POOL_RECYCLE = 3600
    _POOL_TIMEOUT = 10

    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None

    async def connect(self) -> None:
        if self._engine is not None:
            return

        url = settings.BUSINESS_DATABASE_URL
        self._engine = create_async_engine(
            url,
            pool_size=self._POOL_SIZE,
            max_overflow=self._MAX_OVERFLOW,
            pool_recycle=self._POOL_RECYCLE,
            pool_timeout=self._POOL_TIMEOUT,
        )
        logger.info("Business database connected")

    async def disconnect(self) -> None:
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        logger.info("Business database disconnected")

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        async with self._engine.connect() as conn:
            result = await conn.execute(text(sql))
            return [dict(row._mapping) for row in result]

    async def get_table_ddls(self) -> List[Tuple[str, str]]:
        """通过 SQLAlchemy metadata 反射生成每张表的 DDL"""

        def _reflect(sync_conn) -> List[Tuple[str, str]]:
            metadata = MetaData()
            metadata.reflect(bind=sync_conn)
            return [
                (
                    table.name,
                    str(CreateTable(table).compile(sync_conn.engine)),
                )
                for table in metadata.sorted_tables
            ]

        async with self._engine.connect() as conn:
            return await conn.run_sync(_reflect)


business_db = BusinessDatabase()
