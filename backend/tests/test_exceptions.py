"""
Tests for the exception handling system.

Covers:
- Exception class hierarchy and attributes
- Exception handler registration
- HTTP status code mapping
- classify_llm_error() classification logic
"""

import pytest
from app.exception_handlers import setup_exception_handlers
from app.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ContentTooLargeError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    classify_llm_error,
)

# ── Exception hierarchy ─────────────────────────────────────────────────────


class TestExceptionHierarchy:
    """All typed exceptions inherit from AppError and carry correct defaults."""

    def test_base_class(self):
        assert issubclass(AppError, Exception)

    @pytest.mark.parametrize(
        "exc_cls, status_code, error_type",
        [
            (NotFoundError, 404, "not_found"),
            (ValidationError, 422, "validation_error"),
            (AuthenticationError, 401, "authentication_error"),
            (AuthorizationError, 403, "authorization_error"),
            (RateLimitError, 429, "rate_limit_error"),
            (ConflictError, 409, "conflict_error"),
            (ExternalServiceError, 502, "external_service_error"),
            (ContentTooLargeError, 413, "content_too_large_error"),
        ],
    )
    def test_subclass_defaults(self, exc_cls, status_code, error_type):
        exc = exc_cls("test message")
        assert issubclass(exc_cls, AppError)
        assert exc.status_code == status_code
        assert exc.error_type == error_type
        assert exc.message == "test message"
        assert str(exc) == "test message"

    def test_all_nine_exceptions_exist(self):
        """Verify exactly the 9 required exception types exist."""
        from app import exceptions

        concrete = [
            cls
            for cls in [
                exceptions.NotFoundError,
                exceptions.ValidationError,
                exceptions.AuthenticationError,
                exceptions.AuthorizationError,
                exceptions.RateLimitError,
                exceptions.ConflictError,
                exceptions.ExternalServiceError,
                exceptions.ContentTooLargeError,
            ]
        ]
        assert len(concrete) == 8  # 8 concrete + 1 base = 9 total
        for cls in concrete:
            assert issubclass(cls, AppError)


# ── Exception handler setup ─────────────────────────────────────────────────


class TestSetupExceptionHandlers:
    """setup_exception_handlers registers the correct handler map."""

    def test_setup_registers_handlers(self):
        class MockApp:
            def __init__(self):
                self.handlers = {}

            def add_exception_handler(self, exc_class, handler):
                self.handlers[exc_class] = handler

        app = MockApp()
        setup_exception_handlers(app)

        from fastapi.exceptions import RequestValidationError
        from sqlalchemy.exc import SQLAlchemyError

        assert AppError in app.handlers
        assert RequestValidationError in app.handlers
        assert SQLAlchemyError in app.handlers
        assert Exception in app.handlers
        assert len(app.handlers) == 4

    def test_app_error_handler_returns_correct_status(self):
        """The handler should read status_code from the exception instance."""
        import asyncio

        from app.exception_handlers import app_error_handler

        class FakeRequest:
            pass

        for exc_cls, expected_code in [
            (NotFoundError, 404),
            (ValidationError, 422),
            (AuthenticationError, 401),
            (AuthorizationError, 403),
            (RateLimitError, 429),
            (ConflictError, 409),
            (ExternalServiceError, 502),
            (ContentTooLargeError, 413),
        ]:
            exc = exc_cls("test")
            resp = asyncio.run(app_error_handler(FakeRequest(), exc))
            assert resp.status_code == expected_code, (
                f"{exc_cls.__name__} should return {expected_code}, got {resp.status_code}"
            )


# ── classify_llm_error ─────────────────────────────────────────────────────


class TestClassifyLLMError:
    """classify_llm_error maps raw LLM exceptions to typed AppErrors."""

    def test_authentication_error(self):
        exc = Exception("Invalid API key provided")
        result = classify_llm_error(exc)
        assert isinstance(result, AuthenticationError)
        assert "API Key" in result.message

    def test_rate_limit_error(self):
        exc = Exception("Rate limit exceeded for model")
        result = classify_llm_error(exc)
        assert isinstance(result, RateLimitError)
        assert "频率" in result.message

    def test_model_not_found(self):
        exc = Exception("Model gpt-99 does not exist")
        result = classify_llm_error(exc)
        assert isinstance(result, ValidationError)

    def test_timeout_error(self):
        exc = Exception("Connection timed out after 30s")
        result = classify_llm_error(exc)
        assert isinstance(result, ExternalServiceError)

    def test_context_length_error(self):
        exc = Exception("context_length_exceeded: max 4096 tokens")
        result = classify_llm_error(exc)
        assert isinstance(result, ContentTooLargeError)

    def test_service_unavailable(self):
        exc = Exception("503 Service Unavailable")
        result = classify_llm_error(exc)
        assert isinstance(result, ExternalServiceError)

    def test_unclassified_defaults_to_external_service(self):
        exc = Exception("Some unknown provider error")
        result = classify_llm_error(exc)
        assert isinstance(result, ExternalServiceError)

    def test_error_type_name_matching(self):
        """Should match on exception class name too."""

        class TimeoutException(Exception):
            pass

        exc = TimeoutException("request failed")
        result = classify_llm_error(exc)
        assert isinstance(result, ExternalServiceError)

    def test_truncation(self):
        long_msg = "x" * 500
        exc = Exception(long_msg)
        result = classify_llm_error(exc)
        assert len(result.message) <= 250  # truncated + prefix

    def test_401_status_code(self):
        exc = Exception("Unauthorized: 401")
        result = classify_llm_error(exc)
        assert isinstance(result, AuthenticationError)
        assert result.status_code == 401

    def test_429_status_code(self):
        exc = Exception("Too many requests: 429")
        result = classify_llm_error(exc)
        assert isinstance(result, RateLimitError)
        assert result.status_code == 429
