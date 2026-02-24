from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from phoenix.otel import register

from app.agent.graph import build_graph, create_checkpointer
from app.core.config import settings
from app.core.database import business_db, db
from app.core.logger import logger
from app.core.redis import redis_client
from app.services.schema import SchemaService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting application")

    register(
        project_name=settings.PROJECT_NAME,
        endpoint=settings.PHOENIX_COLLECTOR_ENDPOINT,
        auto_instrument=True,
    )
    logger.info("Phoenix tracing initialized")

    await db.connect()
    logger.info("Database connected")

    await business_db.connect()
    logger.info("Business database connected")

    await redis_client.connect()
    logger.info("Redis connected")

    await _auto_sync_schemas()

    with create_checkpointer() as checkpointer:
        app.state.nl2sql_graph = build_graph(checkpointer)
        logger.info("NL2SQL graph initialized")

        yield

    logger.info("Shutting down application")

    await redis_client.disconnect()
    await business_db.disconnect()
    await db.disconnect()

    logger.info("Shutdown completed")


async def _auto_sync_schemas() -> None:
    """启动时检查 Milvus 是否有 schema 数据，没有则自动同步"""
    schema_service = SchemaService()
    if await schema_service.has_schemas():
        logger.info("Schema data already exists, skipping auto-sync")
        return

    logger.info("No schema data found, starting auto-sync")
    try:
        count = await schema_service.sync()
        logger.info("Auto-sync completed", table_count=count)
    except Exception as e:
        logger.error("Auto-sync failed", error=str(e))
