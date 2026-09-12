"""Tests for Langfuse Tracing Module (app/core/tracing.py)."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.tracing import (
    async_trace_span_ctx,
    flush_tracing,
    get_client,
    init_tracing,
    is_tracing_enabled,
    observe_span,
    record_generation,
    shutdown_tracing,
    trace_span_ctx,
    update_current_observation,
    update_current_trace,
)


def test_tracing_disabled_by_default():
    """When LANGFUSE_ENABLED is False or unconfigured, tracing is disabled."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = False

    client = init_tracing(mock_settings)
    assert client is None
    assert not is_tracing_enabled()
    assert get_client() is None


def test_tracing_disabled_when_keys_missing():
    """Enabled=True but empty keys should safely fallback to disabled."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = True
    mock_settings.langfuse_public_key = ""
    mock_settings.langfuse_secret_key = ""

    client = init_tracing(mock_settings)
    assert client is None
    assert not is_tracing_enabled()


def test_tracing_observe_decorator_pass_through():
    """When disabled, observe_span is a zero-overhead pass-through."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = False
    init_tracing(mock_settings)

    @observe_span(name="test_sync")
    def sample_sync(x, y):
        return x + y

    @observe_span(name="test_async")
    async def sample_async(a, b):
        return a * b

    assert sample_sync(2, 3) == 5

    import asyncio

    res = asyncio.run(sample_async(3, 4))
    assert res == 12


def test_trace_span_ctx_no_op():
    """Sync and async context managers gracefully yield NoOpSpan when disabled."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = False
    init_tracing(mock_settings)

    with trace_span_ctx("test.span", input_data="hello") as span:
        span.update(output="world")
        span.score(value=1.0)
        span.end()

    async def _run_async():
        async with async_trace_span_ctx("test.async_span", metadata={"k": "v"}) as span:
            span.update(res="ok")

    import asyncio

    asyncio.run(_run_async())


def test_record_generation_no_op():
    """record_generation executes safely without raising."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = False
    init_tracing(mock_settings)

    record_generation(
        name="test.gen",
        model="gpt-4o",
        input_messages=[{"role": "user", "content": "hi"}],
        output_text="hello",
        usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    )
    update_current_trace(user_id="u123", tags=["test"])
    update_current_observation(input="q", output="a")
    flush_tracing()
    shutdown_tracing()


def test_init_tracing_enabled_with_mock():
    """When properly configured, initializes Langfuse client."""
    mock_settings = MagicMock()
    mock_settings.langfuse_enabled = True
    mock_settings.langfuse_public_key = "pk-lf-test"
    mock_settings.langfuse_secret_key = "sk-lf-test"
    mock_settings.langfuse_host = "https://cloud.langfuse.com"

    import sys

    mock_langfuse_mod = MagicMock()
    mock_instance = MagicMock()
    mock_langfuse_mod.Langfuse.return_value = mock_instance
    with patch.dict(sys.modules, {"langfuse": mock_langfuse_mod}):
        client = init_tracing(mock_settings)
        assert client is mock_instance
        assert is_tracing_enabled()
        assert get_client() is mock_instance

        # Test flush and shutdown
        flush_tracing()
        mock_instance.flush.assert_called_once()

        shutdown_tracing()
        mock_instance.shutdown.assert_called_once()

    # Reset back to disabled for other tests
    init_tracing()
