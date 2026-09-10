"""Langfuse Tracing and Observability Module for Study Copilot.

Provides unified tracing decorators, context managers, and instrumentation helpers.
When LANGFUSE_ENABLED is False (or keys are not provided), all tracing calls are zero-overhead no-ops.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Optional, TypeVar, cast

from app.config import settings

logger = logging.getLogger(__name__)

# Global client singleton
_client: Any = None
_is_enabled: bool = False

F = TypeVar("F", bound=Callable[..., Any])


class NoOpSpan:
    """A dummy span object that safely accepts updates when tracing is disabled."""

    def update(self, **kwargs: Any) -> NoOpSpan:
        return self

    def end(self, **kwargs: Any) -> NoOpSpan:
        return self

    def score(self, **kwargs: Any) -> NoOpSpan:
        return self


def init_tracing(custom_settings: Any = None) -> Any:
    """Initialize Langfuse client. Safe to call multiple times."""
    global _client, _is_enabled

    cfg = custom_settings or settings
    enabled = getattr(cfg, "langfuse_enabled", False)
    pub_key = getattr(cfg, "langfuse_public_key", "").strip()
    sec_key = getattr(cfg, "langfuse_secret_key", "").strip()
    host = getattr(cfg, "langfuse_host", "https://cloud.langfuse.com").strip()

    if not enabled:
        _is_enabled = False
        _client = None
        logger.info("Langfuse tracing is disabled by configuration.")
        return None

    if not pub_key or not sec_key:
        logger.warning(
            "Langfuse enabled=True, but public/secret keys are missing. Tracing will be disabled."
        )
        _is_enabled = False
        _client = None
        return None

    try:
        from langfuse import Langfuse

        _client = Langfuse(public_key=pub_key, secret_key=sec_key, host=host)
        _is_enabled = True
        logger.info("Langfuse tracing successfully initialized (host=%s).", host)
        return _client
    except Exception as e:
        logger.error("Failed to initialize Langfuse client: %s. Falling back to no-op.", e)
        _is_enabled = False
        _client = None
        return None


def is_tracing_enabled() -> bool:
    """Check if Langfuse tracing is active."""
    return _is_enabled and _client is not None


def get_client() -> Any:
    """Return the underlying Langfuse client or None."""
    return _client


def flush_tracing() -> None:
    """Flush pending events to Langfuse if enabled."""
    if is_tracing_enabled() and _client is not None:
        try:
            _client.flush()
        except Exception as e:
            logger.debug("Failed to flush Langfuse events: %s", e)


def shutdown_tracing() -> None:
    """Flush and shut down Langfuse client."""
    if is_tracing_enabled() and _client is not None:
        try:
            _client.shutdown()
        except Exception as e:
            logger.debug("Error shutting down Langfuse: %s", e)


def update_current_trace(
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Update metadata for the current Langfuse trace."""
    if not is_tracing_enabled():
        return
    try:
        from langfuse.decorators import langfuse_context

        langfuse_context.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            metadata=metadata,
        )
    except Exception as e:
        logger.debug("Tracing update_current_trace ignored: %s", e)


def update_current_observation(
    input: Any | None = None,
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    """Update observation fields on the current active span/generation."""
    if not is_tracing_enabled():
        return
    try:
        from langfuse.decorators import langfuse_context

        kwargs: dict[str, Any] = {}
        if input is not None:
            kwargs["input"] = input
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if level is not None:
            kwargs["level"] = level
        if status_message is not None:
            kwargs["status_message"] = status_message

        if kwargs:
            langfuse_context.update_current_observation(**kwargs)
    except Exception as e:
        logger.debug("Tracing update_current_observation ignored: %s", e)


@contextmanager
def trace_span_ctx(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any | None = None,
) -> Generator[Any, None, None]:
    """Sync context manager for a span."""
    if not is_tracing_enabled():
        yield NoOpSpan()
        return

    try:
        from langfuse.decorators import langfuse_context

        with langfuse_context.observe(name=name) as obs:
            if metadata:
                langfuse_context.update_current_observation(metadata=metadata)
            if input_data is not None:
                langfuse_context.update_current_observation(input=input_data)
            yield obs
    except Exception:
        yield NoOpSpan()


@asynccontextmanager
async def async_trace_span_ctx(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any | None = None,
) -> AsyncGenerator[Any, None]:
    """Async context manager for a span."""
    if not is_tracing_enabled():
        yield NoOpSpan()
        return

    try:
        from langfuse.decorators import langfuse_context

        with langfuse_context.observe(name=name) as obs:
            if metadata:
                langfuse_context.update_current_observation(metadata=metadata)
            if input_data is not None:
                langfuse_context.update_current_observation(input=input_data)
            yield obs
    except Exception:
        yield NoOpSpan()


def observe_span(name: str | None = None, as_type: str = "span") -> Callable[[F], F]:
    """Decorator that wraps a function with Langfuse @observe when enabled.

    Works seamlessly on both sync and async functions.
    When tracing is disabled, it acts as a zero-overhead pass-through.
    """

    def decorator(fn: F) -> F:
        if not is_tracing_enabled():
            return fn

        try:
            from langfuse.decorators import observe

            return cast(F, observe(name=name or fn.__name__, as_type=as_type)(fn))
        except Exception:
            return fn

    return decorator


def record_generation(
    name: str,
    model: str,
    input_messages: Any,
    output_text: str,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a standalone LLM generation event if tracing is active."""
    if not is_tracing_enabled() or _client is None:
        return
    try:
        _client.generation(
            name=name,
            model=model,
            input=input_messages,
            output=output_text,
            usage=usage,
            metadata=metadata,
        )
    except Exception as e:
        logger.debug("Failed to record generation to Langfuse: %s", e)
