"""Tests for shared.observability.logging_config."""

from __future__ import annotations

import io
import json
import logging
import uuid

import pytest

from shared.observability.logging_config import (
    ContextFilter,
    RequestContext,
    configure_logging,
    current_request_context,
    reset_request_context,
    set_request_context,
)


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    """Snapshot root logger state so each test starts clean."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


# ---------------------------------------------------------------------------
# Context var
# ---------------------------------------------------------------------------


def test_context_defaults_are_none() -> None:
    ctx = current_request_context()
    assert ctx == RequestContext()
    assert ctx.correlation_id is None
    assert ctx.tenant_id is None
    assert ctx.user_id is None


def test_set_and_reset_request_context() -> None:
    corr = uuid.uuid4()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    token = set_request_context(correlation_id=corr, tenant_id=tenant, user_id=user)
    try:
        ctx = current_request_context()
        assert ctx.correlation_id == corr
        assert ctx.tenant_id == tenant
        assert ctx.user_id == user
    finally:
        reset_request_context(token)
    assert current_request_context() == RequestContext()


# ---------------------------------------------------------------------------
# ContextFilter
# ---------------------------------------------------------------------------


def _make_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def test_filter_injects_none_when_no_context() -> None:
    record = _make_record()
    ContextFilter().filter(record)
    assert record.correlation_id is None
    assert record.tenant_id is None
    assert record.user_id is None


def test_filter_injects_context_when_set() -> None:
    corr = uuid.uuid4()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    token = set_request_context(correlation_id=corr, tenant_id=tenant, user_id=user)
    try:
        record = _make_record()
        assert ContextFilter().filter(record) is True
        assert record.correlation_id == str(corr)
        assert record.tenant_id == str(tenant)
        assert record.user_id == str(user)
    finally:
        reset_request_context(token)


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_json_emits_valid_json_with_context() -> None:
    buf = io.StringIO()
    configure_logging(level="INFO", mode="json", stream=buf)
    corr = uuid.uuid4()
    token = set_request_context(correlation_id=corr, tenant_id=uuid.uuid4())
    try:
        logging.getLogger("test-json").info("payment_processed", extra={"amount": 42})
    finally:
        reset_request_context(token)

    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message"] == "payment_processed"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test-json"
    assert payload["correlation_id"] == str(corr)
    assert payload["tenant_id"] is not None
    assert "timestamp" in payload
    # extra={} fields flow through JsonFormatter's default behaviour
    assert payload["amount"] == 42


def test_configure_json_with_no_context_emits_null_fields() -> None:
    buf = io.StringIO()
    configure_logging(level="INFO", mode="json", stream=buf)
    logging.getLogger("test-none").warning("no_context")
    payload = json.loads(buf.getvalue().strip().splitlines()[0])
    assert payload["correlation_id"] is None
    assert payload["tenant_id"] is None
    assert payload["user_id"] is None


def test_configure_text_mode_is_human_readable() -> None:
    buf = io.StringIO()
    configure_logging(level="DEBUG", mode="text", stream=buf)
    token = set_request_context(correlation_id=uuid.UUID(int=1))
    try:
        logging.getLogger("test-text").debug("hello-world")
    finally:
        reset_request_context(token)
    output = buf.getvalue()
    assert "hello-world" in output
    # Text mode is NOT JSON
    with pytest.raises(json.JSONDecodeError):
        json.loads(output.strip())
    assert "corr=00000000-0000-0000-0000-000000000001" in output


def test_configure_is_idempotent_and_replaces_handlers() -> None:
    configure_logging(level="INFO", mode="json", stream=io.StringIO())
    configure_logging(level="WARNING", mode="text", stream=io.StringIO())
    root = logging.getLogger()
    # Only one handler after two configures
    assert len(root.handlers) == 1
    assert root.level == logging.WARNING


def test_configure_accepts_int_level() -> None:
    buf = io.StringIO()
    configure_logging(level=logging.ERROR, mode="json", stream=buf)
    logging.getLogger("t").info("ignored")
    logging.getLogger("t").error("kept")
    lines = [line for line in buf.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "kept"


def test_configure_default_stream_is_stderr() -> None:
    """When stream is None, handler writes to sys.stderr — we don't capture
    that here, just verify construction doesn't crash."""
    configure_logging(level="INFO", mode="json", stream=None)
    # StreamHandler stores the stream
    root = logging.getLogger()
    assert root.handlers[0].stream is not None
