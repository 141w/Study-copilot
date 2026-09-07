"""Structured logging setup - stdlib only, zero extra dependencies.

Production (settings.debug=False): one JSON object per line on stdout,
carrying ts / level / logger / message / trace_id - ELK/Loki friendly.
Development: concise human-readable text.

The active trace_id lives in a ContextVar set by TraceIdMiddleware;
any log line emitted during request handling automatically carries it.
"""

import json
import logging
import sys
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(debug=True, level="INFO", force=False):
    """Configure root logging once at startup.

    Args:
        debug: True -> dev text format; False -> production JSON lines.
        level: Root logger level name (case-insensitive: "DEBUG", "info", etc.) or int.
        force: If True, overwrite root.handlers even if already set.
    """
    handler = logging.StreamHandler(sys.stdout)
    if debug:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    # Only set handlers if none exist or force=True (avoid stomping pytest / uvicorn handlers).
    if force or not root.handlers:
        root.handlers = [handler]

    if isinstance(level, str):
        level = getattr(logging, level.strip().upper(), logging.INFO)
    root.setLevel(level)
