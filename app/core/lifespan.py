from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import db
from app.core.logger import logger
from app.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _ = app  # FastAPI requires app parameter
    logger.info("Starting application")

    await db.connect()
    logger.info("Database connected")

    await redis_client.connect()
    logger.info("Redis connected")

    yield

    logger.info("Shutting down application")

    await redis_client.disconnect()
    await db.disconnect()

    logger.info("Shutdown completed")
