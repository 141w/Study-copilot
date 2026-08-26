"""Tests for TraceIdMiddleware - pure ASGI unit tests, no full app import."""

import json
import logging

import pytest

from app.middleware.trace import TraceIdMiddleware


def make_scope(headers=None):
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.encode(), v.encode()) for k, v in (headers or {}).items()],
    }


async def dummy_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b"ok"})


def get_response_headers(messages):
    start = next(m for m in messages if m["type"] == "http.response.start")
    return {k.decode().lower(): v.decode() for k, v in start["headers"]}


@pytest.mark.asyncio
async def test_generates_trace_id_when_missing():
    app = TraceIdMiddleware(dummy_app)
    messages = []
    await app(make_scope(), None, messages.append)

    headers = get_response_headers(messages)
    assert len(headers["x-trace-id"]) == 32  # uuid4 hex
    assert "x-process-time-ms" in headers


@pytest.mark.asyncio
async def test_honors_incoming_trace_id():
    app = TraceIdMiddleware(dummy_app)
    messages = []
    await app(make_scope({"X-Trace-ID": "my-trace-123"}), None, messages.append)

    headers = get_response_headers(messages)
    assert headers["x-trace-id"] == "my-trace-123"


@pytest.mark.asyncio
async def test_non_http_scope_passes_through():
    called = []

    async def recorder(scope, receive, send):
        called.append(scope["type"])

    app = TraceIdMiddleware(recorder)
    await app({"type": "lifespan"}, None, None)
    assert called == ["lifespan"]


@pytest.mark.asyncio
async def test_trace_id_visible_to_logging_contextvar():
    from app.core.logger import trace_id_var

    captured = {}

    async def probing_app(scope, receive, send):
        captured["trace_id"] = trace_id_var.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})

    app = TraceIdMiddleware(probing_app)
    await app(make_scope({"X-Trace-ID": "log-corr-9"}), None, lambda m: None)

    assert captured["trace_id"] == "log-corr-9"
