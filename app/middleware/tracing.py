import uuid
from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import bind_context, clear_context


class TracingMiddleware(BaseHTTPMiddleware):
    TRACE_HEADERS = [
        "X-Trace-ID",
        "X-Request-ID",
        "X-Correlation-ID",
    ]

    def __init__(
        self,
        app,
        header_name: str = "X-Trace-ID",
        generate_if_missing: bool = True,
    ) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.generate_if_missing = generate_if_missing

    def _extract_trace_id(self, request: Request) -> Optional[str]:
        for header in self.TRACE_HEADERS:
            trace_id = request.headers.get(header)
            if trace_id:
                return trace_id

        traceparent = request.headers.get("traceparent")
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 2:
                return parts[1]

        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = self._extract_trace_id(request)

        if not trace_id and self.generate_if_missing:
            trace_id = uuid.uuid4().hex

        if trace_id:
            bind_context(trace_id=trace_id)
            request.state.trace_id = trace_id

        try:
            response = await call_next(request)

            if trace_id:
                response.headers[self.header_name] = trace_id

            return response
        finally:
            clear_context()

