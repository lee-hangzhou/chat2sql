from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.lifespan import lifespan
from app.exceptions.handlers import register_exception_handlers
from app.middleware import (
    JWTAuthMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    TracingMiddleware,
    setup_cors,
)

# 前端构建产物目录
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    setup_cors(application)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(TracingMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        JWTAuthMiddleware,
        whitelist=[
            f"{settings.API_V1_PREFIX}/auth/login",
            f"{settings.API_V1_PREFIX}/auth/register",
            f"{settings.API_V1_PREFIX}/auth/refresh",
            f"{settings.API_V1_PREFIX}/openapi.json",
        ],
        whitelist_prefixes=[
            f"{settings.API_V1_PREFIX}/health",
            "/docs",
            "/redoc",
            "/assets",
            "/favicon",
        ],
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # 挂载前端静态文件（仅在构建产物存在时生效）
    if _FRONTEND_DIR.is_dir():
        application.mount(
            "/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend"
        )

    return application


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)
