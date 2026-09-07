"""Tests for structured logging (JSON formatter + setup)."""

import json
import logging

from app.core.logger import JsonFormatter, setup_logging, trace_id_var


def make_record(msg="hello", level=logging.INFO):
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_json_formatter_outputs_parseable_json():
    line = JsonFormatter().format(make_record("structured message"))
    payload = json.loads(line)  # must not raise
    assert payload["message"] == "structured message"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"


def test_json_formatter_includes_trace_id():
    token = trace_id_var.set("corr-42")
    try:
        payload = json.loads(JsonFormatter().format(make_record()))
        assert payload["trace_id"] == "corr-42"
    finally:
        trace_id_var.reset(token)


def test_default_trace_id_is_dash():
    payload = json.loads(JsonFormatter().format(make_record()))
    assert payload["trace_id"] == "-"


def test_setup_logging_production_installs_json_handler():
    root = logging.getLogger()
    original = root.handlers[:]
    # Clear handlers so setup_logging can install its own (mimics fresh process).
    root.handlers = []
    try:
        setup_logging(debug=False)
        assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers if h.formatter)
    finally:
        root.handlers = original


def test_setup_logging_debug_uses_text_format():
    root = logging.getLogger()
    original = root.handlers[:]
    root.handlers = []
    try:
        setup_logging(debug=True)
        fmts = [
            h.formatter._fmt for h in root.handlers if h.formatter and hasattr(h.formatter, "_fmt")
        ]
        assert any("%(asctime)s" in f for f in fmts)
    finally:
        root.handlers = original


def test_setup_logging_respects_level_and_case_insensitive():
    root = logging.getLogger()
    original_level = root.level
    try:
        setup_logging(level="debug")
        assert root.level == logging.DEBUG

        setup_logging(level="WARNING")
        assert root.level == logging.WARNING

        setup_logging(level=logging.ERROR)
        assert root.level == logging.ERROR
    finally:
        root.setLevel(original_level)


def test_setup_logging_invalid_level_falls_back_to_info():
    root = logging.getLogger()
    original_level = root.level
    try:
        setup_logging(level="NONEXISTENT_LEVEL")
        assert root.level == logging.INFO
    finally:
        root.setLevel(original_level)


def test_setup_logging_preserves_existing_handlers_unless_forced():
    root = logging.getLogger()
    original = root.handlers[:]
    sentinel_handler = logging.NullHandler()
    root.handlers = [sentinel_handler]
    try:
        # Default force=False: should NOT overwrite sentinel_handler
        setup_logging(debug=True, force=False)
        assert root.handlers == [sentinel_handler]

        # force=True: should overwrite sentinel_handler
        setup_logging(debug=True, force=True)
        assert sentinel_handler not in root.handlers
        assert len(root.handlers) == 1
    finally:
        root.handlers = original
