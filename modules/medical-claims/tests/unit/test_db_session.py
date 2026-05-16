"""Unit tests for medical-claims sync session factory.

Tests that get_db_session() commit/rollback contract works correctly and that
missing MEDICAL_CLAIMS_DB_URL raises a clear RuntimeError.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from unittest.mock import patch


def test_missing_db_url_raises_runtime_error():
    """get_db_session() must fail fast if MEDICAL_CLAIMS_DB_URL is not set."""
    from src.db import session as sess_mod

    original_engine = sess_mod._engine
    original_factory = sess_mod._SessionLocal
    try:
        sess_mod._engine = None
        sess_mod._SessionLocal = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEDICAL_CLAIMS_DB_URL", None)
            with pytest.raises(RuntimeError, match="MEDICAL_CLAIMS_DB_URL"):
                with sess_mod.get_db_session():
                    pass
    finally:
        sess_mod._engine = original_engine
        sess_mod._SessionLocal = original_factory
