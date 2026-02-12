import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import structlog


@asynccontextmanager
async def log_elapsed(log: structlog.stdlib.BoundLogger, event: str, **extra: Any):
    """异步上下文管理器：记录代码段耗时，支持在块内追加日志字段"""
    ctx: dict[str, Any] = {}
    start = time.monotonic()
    yield ctx
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    log.info(event, elapsed_ms=elapsed_ms, **extra, **ctx)


@contextmanager
def log_elapsed_sync(log: structlog.stdlib.BoundLogger, event: str, **extra: Any):
    """同步上下文管理器：记录代码段耗时，支持在块内追加日志字段"""
    ctx: dict[str, Any] = {}
    start = time.monotonic()
    yield ctx
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    log.info(event, elapsed_ms=elapsed_ms, **extra, **ctx)
