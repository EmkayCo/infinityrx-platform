"""Unit tests for the audit chain verification job (H-07 / HIPAA 2026).

Tests use a mock DB session to avoid requiring a real PostgreSQL connection.
The hash chain logic is verified with known-good and tampered entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.audit.hash_chain import GENESIS_HASH, compute_entry_hash
from src.jobs.verify_audit_chain_job import _verify_tenant_chain


_TENANT_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


def _now():
    return datetime.now(tz=timezone.utc)


def _make_row(
    row_id: int,
    tenant_id: str,
    action: str,
    previous_hash: str,
    entry_hash: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> tuple:
    """Build a fake DB row tuple matching the SELECT column order."""
    return (
        row_id,
        uuid.UUID(tenant_id),
        action,
        entity_type,
        entity_id,
        _now(),
        previous_hash,
        entry_hash,
    )


def _compute_hash(tenant_id: str, action: str, created_at: datetime, previous_hash: str) -> str:
    return compute_entry_hash(
        tenant_id=uuid.UUID(tenant_id),
        action=action,
        entity_type=None,
        entity_id=None,
        created_at=created_at,
        previous_hash=previous_hash,
    )


class TestVerifyTenantChainOk:
    """Valid chain — should report zero failures."""

    def test_empty_chain_reports_zero_entries(self) -> None:
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)
        assert result["entries_checked"] == 0
        assert result["failures"] == []

    def test_single_valid_genesis_entry(self) -> None:
        ts = _now()
        entry_hash = _compute_hash(_TENANT_ID, "login", ts, GENESIS_HASH)
        row = (1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, entry_hash)

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [row]
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 1
        assert result["failures"] == []

    def test_two_valid_entries_chained(self) -> None:
        ts1 = _now()
        ts2 = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts1, GENESIS_HASH)
        h2 = _compute_hash(_TENANT_ID, "logout", ts2, h1)

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, h1),
            (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, h1, h2),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 2
        assert result["failures"] == []


class TestVerifyTenantChainTamperedEntries:
    """Tampered chain — should report failures without raising."""

    def test_single_tampered_entry_reports_failure(self) -> None:
        ts = _now()
        tampered_hash = "a" * 64  # not the correct SHA-256

        row = (1, uuid.UUID(_TENANT_ID), "login", None, None, ts, GENESIS_HASH, tampered_hash)
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [row]
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 1
        assert len(result["failures"]) == 1
        failure = result["failures"][0]
        assert failure["entry_id"] == 1
        assert failure["tenant_id"] == _TENANT_ID
        assert failure["stored_hash"] == tampered_hash

    def test_tampered_middle_entry_causes_failure_and_cascades(self) -> None:
        """Tampering row 2 breaks row 2 AND row 3 (cascade)."""
        ts1 = _now()
        ts2 = _now()
        ts3 = _now()
        h1 = _compute_hash(_TENANT_ID, "login", ts1, GENESIS_HASH)
        tampered_h2 = "b" * 64
        # Row 3 is built against the correct h2, but since h2 is tampered it will
        # also fail verification.
        h2_real = _compute_hash(_TENANT_ID, "update", ts2, h1)
        h3 = _compute_hash(_TENANT_ID, "logout", ts3, h2_real)

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, h1),
            (2, uuid.UUID(_TENANT_ID), "update", None, None, ts2, h1, tampered_h2),
            (3, uuid.UUID(_TENANT_ID), "logout", None, None, ts3, tampered_h2, h3),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=False)

        assert result["entries_checked"] == 3
        # Rows 2 and 3 should both fail (cascade from tampering row 2)
        assert len(result["failures"]) == 2
        assert result["failures"][0]["entry_id"] == 2
        assert result["failures"][1]["entry_id"] == 3

    def test_stop_on_first_failure_stops_early(self) -> None:
        ts1 = _now()
        ts2 = _now()
        tampered_h1 = "c" * 64
        h2 = "d" * 64

        rows = [
            (1, uuid.UUID(_TENANT_ID), "login", None, None, ts1, GENESIS_HASH, tampered_h1),
            (2, uuid.UUID(_TENANT_ID), "logout", None, None, ts2, tampered_h1, h2),
        ]
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = rows
        result = _verify_tenant_chain(db, tenant_id=_TENANT_ID, stop_on_first=True)

        # Only 1 failure reported — stopped after first broken link
        assert result["entries_checked"] == 1
        assert len(result["failures"]) == 1
        assert result["failures"][0]["entry_id"] == 1


class TestJobHandlerRegistered:
    """Verify the job handler is registered under the expected type."""

    def test_handler_registered(self) -> None:
        from src.jobs.registry import default_registry
        # Importing the module registers the handler via @job_handler decorator.
        import src.jobs.verify_audit_chain_job  # noqa: F401

        handler = default_registry.get("audit.verify_chain")
        assert callable(handler)
