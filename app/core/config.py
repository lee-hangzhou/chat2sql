from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    PROJECT_NAME: str = "smart_chat"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    ENV: str = Field(default="dev")
    DEBUG: bool = Field(default=False)
    PORT: int = Field(default=8000)

    # Default to SQLite for development (change in production)

    DATABASE_URL: str = Field(default="sqlite://./smart_chat.db")

    # Business database for NL2SQL query validation (optional)
    BUSINESS_DATABASE_URL: Optional[str] = Field(default="mysql://root:123456@localhost:3306/ai_translator", description="业务数据库连接地址，供 NL2SQL 查询验证使用")
    EXPLAIN_MAX_ROWS: int = Field(default=10000, description="EXPLAIN 预估扫描行数阈值，超过则标记为性能问题")
    AGENT_MAX_RETRIES: int = Field(default=3, description="SQL 校验失败最大重试次数")


    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=10)

    # CHANGE THIS IN PRODUCTION!
    JWT_SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    CORS_ORIGINS: str = Field(default="")

    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")

    # NL2SQL Agent
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key，供 clarify/parse/sql_generate 等节点使用")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI 模型名")
    OPENAI_BASE_URL: Optional[str] = Field(default=None, description="OpenAI 兼容 API 的 base_url，可选")

    # milvus配置
    MILVUS_HOST: str = Field(default="localhost")
    MILVUS_PORT: int = Field(default=19530)
    EMBEDDING_MODEL:str = Field(default="BAAI/bge-large-zh-v1.5")



    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
