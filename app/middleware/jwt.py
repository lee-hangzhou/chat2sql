from typing import Callable, List, Optional, Set

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import logger
from app.core.redis import redis_client
from app.core.security import active_token_key, decode_token


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        whitelist: Optional[List[str]] = None,
        whitelist_prefixes: Optional[List[str]] = None,
    ) -> None:
        super().__init__(app)
        self.whitelist: Set[str] = set(whitelist or [])
        self.whitelist_prefixes: List[str] = whitelist_prefixes or []

    def _is_whitelisted(self, path: str) -> bool:
        if path in self.whitelist:
            return True

        for prefix in self.whitelist_prefixes:
            if path.startswith(prefix):
                return True

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if self._is_whitelisted(path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "msg": "Missing authorization header",
                    "data": None,
                },
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "msg": "Invalid authorization header format",
                    "data": None,
                },
            )

        token = auth_header[7:]  # Remove "Bearer " prefix
        payload = decode_token(token)

        if not payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "msg": "Invalid or expired token",
                    "data": None,
                },
            )

        if payload.get("type") != "access":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "msg": "Invalid token type",
                    "data": None,
                },
            )

        # 双重校验：JWT 签名通过后，再验证 Redis 中 token 是否存活
        try:
            if not await redis_client.exists(active_token_key(token)):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "code": 401,
                        "msg": "Token not active or already revoked",
                        "data": None,
                    },
                )
        except Exception:
            logger.warning("jwt.redis_check_failed", path=path)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "code": 503,
                    "msg": "Authentication service temporarily unavailable",
                    "data": None,
                },
            )

        request.state.user_id = payload.get("sub")
        request.state.user_roles = payload.get("roles", [])
        request.state.token_payload = payload

        return await call_next(request)
