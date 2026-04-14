"""Tests for shared.observability.slow_query.install_slow_query_logger."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from shared.observability.slow_query import install_slow_query_logger


class _Base(DeclarativeBase):
    pass


class _Widget(_Base):
    __tablename__ = "widgets"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_fast_query_not_logged(engine, caplog) -> None:
    install_slow_query_logger(engine, threshold_ms=1000)
    with caplog.at_level(logging.WARNING, logger="shared.observability.slow_query"):
        with Session(engine) as s:
            s.execute(text("SELECT 1"))
    assert not any("slow_query" in m for m in caplog.messages)


def test_slow_query_is_logged(engine, caplog) -> None:
    """Fake elapsed time via monkeypatching time.perf_counter."""
    install_slow_query_logger(engine, threshold_ms=100)

    # Monkeypatch perf_counter so the 'after' call reports 500ms elapsed
    # regardless of real wall time. Implementation reads perf_counter
    # twice (before + after) — we return increasing values.
    seq = iter([0.0, 0.5, 0.0, 0.5, 0.0, 0.5])  # plenty for any internal retries

    with patch("shared.observability.slow_query.time.perf_counter", lambda: next(seq)):
        with caplog.at_level(logging.WARNING, logger="shared.observability.slow_query"):
            with Session(engine) as s:
                s.execute(text("SELECT 1"))

    slow_records = [r for r in caplog.records if "slow_query" in r.message]
    assert len(slow_records) >= 1
    rec = slow_records[0]
    assert getattr(rec, "elapsed_ms") >= 100
    assert getattr(rec, "threshold_ms") == 100


def test_parameters_are_not_logged_raw(engine, caplog) -> None:
    """PHI-safety: the listener must never log parameter values."""
    install_slow_query_logger(engine, threshold_ms=0)  # log every query

    with caplog.at_level(logging.WARNING, logger="shared.observability.slow_query"):
        with Session(engine) as s:
            s.execute(text("SELECT :secret"), {"secret": "SSN-123-45-6789"})

    messages = "\n".join(caplog.messages)
    assert "SSN-123-45-6789" not in messages
    # But param_count should be on the record
    slow_records = [r for r in caplog.records if "slow_query" in r.message]
    assert slow_records
    assert getattr(slow_records[-1], "param_count") >= 1


def test_long_statement_is_truncated(engine, caplog) -> None:
    """Huge statements are truncated to 2000 chars to keep logs bounded."""
    install_slow_query_logger(engine, threshold_ms=0)
    # Build a 3000-char identifier list for SELECT
    big_select = "SELECT " + ", ".join(f"'{'x' * 10}' AS c{i}" for i in range(250))
    assert len(big_select) > 2000

    with caplog.at_level(logging.WARNING, logger="shared.observability.slow_query"):
        with Session(engine) as s:
            s.execute(text(big_select))

    slow_records = [r for r in caplog.records if "slow_query" in r.message]
    assert slow_records
    stmt = getattr(slow_records[-1], "statement")
    assert len(stmt) <= 2001  # 2000 + ellipsis
    assert stmt.endswith("…")


def test_threshold_zero_logs_everything(engine, caplog) -> None:
    install_slow_query_logger(engine, threshold_ms=0)
    with caplog.at_level(logging.WARNING, logger="shared.observability.slow_query"):
        with Session(engine) as s:
            s.execute(text("SELECT 1"))
            s.execute(text("SELECT 2"))
    slow_records = [r for r in caplog.records if "slow_query" in r.message]
    assert len(slow_records) >= 2
