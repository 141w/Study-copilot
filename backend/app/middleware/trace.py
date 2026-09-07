"""Trace-id propagation middleware - pure ASGI, SSE-safe.

Pure ASGI (not BaseHTTPMiddleware) so streaming responses pass through
untouched: SSE token streams are never buffered by an interceptor body.

Behavior:
- Honors incoming X-Trace-ID; generates uuid4 hex otherwise.
- Exposes the id to logging via trace_id ContextVar (see app.core.logger).
- Echoes X-Trace-ID and X-Process-Time-Ms on every response.
"""

import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders

# Shared with app.core.logger so log records pick the id up automatically.
# Imported lazily to keep this module importable without the logger module.
try:
    from app.core.logger import trace_id_var
except ImportError:  # standalone use (tests) without logger module
    trace_id_var = ContextVar("trace_id", default="-")


class TraceIdMiddleware:
    """ASGI middleware attaching a correlation id to each request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []
        }
        trace_id = req_headers.get("x-trace-id") or uuid.uuid4().hex

        token = trace_id_var.set(trace_id)
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                elapsed_ms = f"{(time.perf_counter() - start) * 1000:.1f}"
                headers = MutableHeaders(scope=message)
                headers["X-Trace-ID"] = trace_id
                headers["X-Process-Time-Ms"] = elapsed_ms
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            trace_id_var.reset(token)
