"""
Typed exception hierarchy for Study-copilot.

All custom exceptions inherit from AppError, which carries a default
HTTP status code and a machine-readable error type string.
"""


class AppError(Exception):
    """Base exception for the application.

    Attributes:
        message: Human-readable description.
        status_code: Default HTTP status for this error category.
        error_type: Short machine-readable type (e.g. "not_found").
    """

    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource cannot be located."""

    status_code = 404
    error_type = "not_found"


class ValidationError(AppError):
    """Raised when input data fails validation."""

    status_code = 422
    error_type = "validation_error"


class AuthenticationError(AppError):
    """Raised when credentials are missing or invalid."""

    status_code = 401
    error_type = "authentication_error"


class AuthorizationError(AppError):
    """Raised when the authenticated user lacks permission."""

    status_code = 403
    error_type = "authorization_error"


class RateLimitError(AppError):
    """Raised when a rate limit is exceeded."""

    status_code = 429
    error_type = "rate_limit_error"


class ConflictError(AppError):
    """Raised when an operation conflicts with current state."""

    status_code = 409
    error_type = "conflict_error"


class ExternalServiceError(AppError):
    """Raised when an external service (e.g. LLM provider) fails."""

    status_code = 502
    error_type = "external_service_error"


class ContentTooLargeError(AppError):
    """Raised when the request payload exceeds size limits."""

    status_code = 413
    error_type = "content_too_large_error"


# ---------------------------------------------------------------------------
# LLM error classification
# ---------------------------------------------------------------------------

# Rules: (keywords, exception_class, user_message | None → pass through original)
_CLASSIFICATION_RULES: list[tuple[list[str], type[AppError], str | None]] = [
    # Authentication
    (
        ["authentication", "unauthorized", "invalid api key", "invalid_api_key", "401"],
        AuthenticationError,
        "认证失败，请检查 API Key 设置。",
    ),
    # Rate limit
    (
        ["rate limit", "rate_limit", "429", "too many requests", "quota exceeded"],
        RateLimitError,
        "请求频率超限，请稍后再试。",
    ),
    # Billing / insufficient balance（供应商计费类失败——402 未在前述规则覆盖）
    (
        [
            "402",
            "insufficient balance",
            "insufficient_quota",
            "insufficient quota",
            "billing",
            "payment required",
        ],
        ExternalServiceError,
        "AI 服务余额不足或计费异常，请检查账户额度或更换模型提供商。",
    ),
    # Model configuration
    (
        ["model not found", "does not exist", "model_not_found"],
        ValidationError,
        None,
    ),
    (
        ["no model configured", "please go to settings"],
        ValidationError,
        None,
    ),
    # Network
    (
        [
            "connecterror",
            "timeoutexception",
            "connection refused",
            "connection error",
            "timed out",
            "timeout",
        ],
        ExternalServiceError,
        "无法连接到 AI 服务，请检查网络和配置。",
    ),
    # Context / token limit
    (
        [
            "context length",
            "token limit",
            "maximum context",
            "context_length_exceeded",
            "max_tokens",
        ],
        ContentTooLargeError,
        "内容过长，超出模型上下文限制。请减少内容量或使用更大上下文窗口的模型。",
    ),
    # Payload too large
    (
        ["413", "payload too large", "request entity too large"],
        ContentTooLargeError,
        "请求内容过大，请减少内容量。",
    ),
    # Provider availability
    (
        ["500", "502", "503", "service unavailable", "overloaded", "internal server error"],
        ExternalServiceError,
        "AI 服务暂时不可用，请稍后重试。",
    ),
]


def _truncate(text: str, max_length: int = 200) -> str:
    """Truncate *text* to avoid leaking verbose internal details."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def classify_llm_error(exception: BaseException) -> AppError:
    """Classify a raw LLM-provider exception into a typed :class:`AppError`.

    Parameters
    ----------
    exception:
        Any exception raised by an LLM SDK / HTTP client.

    Returns
    -------
    AppError
        An instance of the most appropriate :class:`AppError` subclass,
        with a user-friendly Chinese message.
    """
    error_str = str(exception).lower()
    error_type_name = type(exception).__name__.lower()
    combined = f"{error_type_name}: {error_str}"

    for keywords, exc_class, message in _CLASSIFICATION_RULES:
        for keyword in keywords:
            if keyword in combined:
                user_message = message if message is not None else _truncate(str(exception))
                return exc_class(user_message)

    # Unclassified – default to ExternalServiceError
    return ExternalServiceError(f"AI 服务错误: {_truncate(str(exception))}")
