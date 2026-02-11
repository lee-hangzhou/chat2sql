from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        frame_options: str = "DENY",
        content_security_policy: Optional[str] = None,
        hsts_max_age: Optional[int] = None,
        referrer_policy: str = "strict-origin-when-cross-origin",
    ) -> None:
        super().__init__(app)
        self.frame_options = frame_options
        self.content_security_policy = content_security_policy
        self.hsts_max_age = hsts_max_age
        self.referrer_policy = referrer_policy

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = self.referrer_policy

        if self.content_security_policy:
            response.headers["Content-Security-Policy"] = self.content_security_policy

        if self.hsts_max_age is not None:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )

        return response

