"""Unit tests for src/api/errors.py (SP-3 A4 — build_error_envelope + correlation_id contextvar)."""
from __future__ import annotations

import re
import uuid

import pytest

from src.api.errors import (
    build_error_envelope,
    get_correlation_id,
    set_correlation_id,
)


# ── build_error_envelope ───────────────────────────────────────────────────────

def test_envelope_has_required_keys():
    env = build_error_envelope("SOME_CODE", "Some message")
    assert "error" in env
    err = env["error"]
    assert "code" in err
    assert "message" in err
    assert "field" in err
    assert "correlation_id" in err


def test_envelope_code_and_message():
    env = build_error_envelope("NOT_FOUND", "Resource not found.")
    assert env["error"]["code"] == "NOT_FOUND"
    assert env["error"]["message"] == "Resource not found."


def test_envelope_field_defaults_to_none():
    env = build_error_envelope("SOME_CODE", "msg")
    assert env["error"]["field"] is None


def test_envelope_field_passed_through():
    env = build_error_envelope("INVALID", "bad", field="x-tenant-id")
    assert env["error"]["field"] == "x-tenant-id"


def test_envelope_correlation_id_explicit():
    cid = str(uuid.uuid4())
    env = build_error_envelope("CODE", "msg", correlation_id=cid)
    assert env["error"]["correlation_id"] == cid


def test_envelope_correlation_id_generated_when_absent():
    """Falls back to a fresh UUID if no contextvar or explicit arg."""
    set_correlation_id(None)
    env = build_error_envelope("CODE", "msg")
    cid = env["error"]["correlation_id"]
    # Must be a valid UUID4 string
    assert re.fullmatch(r"[0-9a-f-]{36}", cid)


def test_envelope_uses_contextvar_when_set():
    fixed_cid = "aaaaaaaa-0000-4000-8000-000000000001"
    set_correlation_id(fixed_cid)
    try:
        env = build_error_envelope("CODE", "msg")
        assert env["error"]["correlation_id"] == fixed_cid
    finally:
        set_correlation_id(None)


def test_explicit_correlation_id_overrides_contextvar():
    set_correlation_id("will-be-ignored")
    try:
        explicit = str(uuid.uuid4())
        env = build_error_envelope("CODE", "msg", correlation_id=explicit)
        assert env["error"]["correlation_id"] == explicit
    finally:
        set_correlation_id(None)


# ── correlation_id contextvar ──────────────────────────────────────────────────

def test_get_correlation_id_returns_none_by_default():
    set_correlation_id(None)
    assert get_correlation_id() is None


def test_set_and_get_correlation_id():
    cid = "bbbbbbbb-1111-4000-8000-000000000002"
    set_correlation_id(cid)
    assert get_correlation_id() == cid
    set_correlation_id(None)
    assert get_correlation_id() is None
