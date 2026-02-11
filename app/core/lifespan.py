from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.graph import build_graph, create_checkpointer
from app.core.database import db
from app.core.logger import logger
from app.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting application")

    await db.connect()
    logger.info("Database connected")

    await redis_client.connect()
    logger.info("Redis connected")

    with create_checkpointer() as checkpointer:
        app.state.nl2sql_graph = build_graph(checkpointer)
        logger.info("NL2SQL graph initialized")

        yield

    logger.info("Shutting down application")

    await redis_client.disconnect()
    await db.disconnect()

    logger.info("Shutdown completed")
