from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from tortoise import Tortoise

from app.core.config import settings
from app.core.logger import logger
from app.core.singleton import Singleton


class Database(Singleton):
    def __init__(self) -> None:
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @staticmethod
    def _add_pool_params(base_url: str) -> str:
        """Add connection pool parameters to database URL."""
        # SQLite doesn't support connection pooling
        if base_url.startswith("sqlite"):
            return base_url

        parsed = urlparse(base_url)
        params = parse_qs(parsed.query)

        pool_config = {
            "minsize": 5,
            "maxsize": 20,
            "connect_timeout": 10,
            "pool_recycle": 3600,
        }

        for key, value in pool_config.items():
            if key not in params:
                params[key] = [str(value)]

        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

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

        if settings.BUSINESS_DATABASE_URL:
            tortoise_config["connections"]["business"] = self._add_pool_params(
                settings.BUSINESS_DATABASE_URL
            )

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
    """业务数据库连接，供 NL2SQL 查询验证使用"""

    _CONNECTION_NAME = "business"

    @property
    def is_configured(self) -> bool:
        """是否已配置业务数据库"""
        return bool(settings.BUSINESS_DATABASE_URL)

    def get_connection(self):
        """获取业务数据库的 Tortoise 连接"""
        if not self.is_configured:
            raise RuntimeError(
                "Business database not configured. Set BUSINESS_DATABASE_URL in environment."
            )
        return Tortoise.get_connection(self._CONNECTION_NAME)


business_db = BusinessDatabase()
