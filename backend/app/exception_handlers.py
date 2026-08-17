"""
Global exception handlers for FastAPI.

Maps each typed exception from :mod:`app.exceptions` to the correct HTTP
status code and JSON payload, and keeps backward-compatible handlers for
FastAPI validation errors and SQLAlchemy errors.
"""

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import AppError

logger = logging.getLogger(__name__)


# ── Typed exception handler ─────────────────────────────────────────────────


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle all typed application errors."""
    logger.warning("AppError [%s]: %s", exc.error_type, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "type": exc.error_type},
    )


# ── FastAPI / Pydantic validation errors ────────────────────────────────────


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic / FastAPI request validation errors."""
    errors = exc.errors()
    error_msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    logger.warning("Validation error: %s", error_msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": error_msg, "type": "validation_error"},
    )


# ── Database errors ─────────────────────────────────────────────────────────


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy errors."""
    logger.error("Database error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "数据库操作失败", "type": "database_error"},
    )


# ── Catch-all ───────────────────────────────────────────────────────────────


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any unhandled exception."""
    logger.error("Unhandled error: %s", exc)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "服务器内部错误", "type": "internal_error"},
    )


# ── Registration helper ─────────────────────────────────────────────────────


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on *app*."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)  # type: ignore[arg-type]
