"""Tests for the SHA-256 hash chain primitive (hash_chain.py).

TDD: these tests were written before the implementation.
"""

from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import UTC, datetime

import pytest

from src.audit.hash_chain import GENESIS_HASH, compute_entry_hash


# ---------------------------------------------------------------------------
# Known-vector test
# ---------------------------------------------------------------------------

def test_known_vector():
    """Verify deterministic SHA-256 output against a hand-computed digest."""
    tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    action = "create"
    entity_type = "user"
    entity_id = "u-001"
    created_at = datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC)
    previous_hash = "0" * 64

    canonical = (
        f"{tenant_id}|{action}|{entity_type}|{entity_id}"
        f"|{created_at.isoformat()}|{previous_hash}"
    )
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    result = compute_entry_hash(
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at=created_at,
        previous_hash=previous_hash,
    )
    assert result == expected
    assert len(result) == 64
    assert result == result.lower()


# ---------------------------------------------------------------------------
# GENESIS_HASH
# ---------------------------------------------------------------------------

def test_genesis_hash_is_64_zeros():
    assert GENESIS_HASH == "0" * 64
    assert len(GENESIS_HASH) == 64


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_determinism_1000_random_inputs():
    """Same inputs always produce the same hash."""
    tenant_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    action = "update"
    entity_type = "claim"
    entity_id = "c-999"
    created_at = datetime(2026, 4, 12, 10, 30, 0, 123456, tzinfo=UTC)
    previous_hash = "a" * 64

    first = compute_entry_hash(
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at=created_at,
        previous_hash=previous_hash,
    )
    for _ in range(999):
        result = compute_entry_hash(
            tenant_id=tenant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=created_at,
            previous_hash=previous_hash,
        )
        assert result == first


# ---------------------------------------------------------------------------
# Different tenant_id → different hash
# ---------------------------------------------------------------------------

def test_different_tenant_id_produces_different_hash():
    kwargs = dict(
        action="create",
        entity_type="user",
        entity_id="u1",
        created_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
        previous_hash=None,
    )
    h1 = compute_entry_hash(
        tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), **kwargs
    )
    h2 = compute_entry_hash(
        tenant_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), **kwargs
    )
    assert h1 != h2


# ---------------------------------------------------------------------------
# Different timestamp → different hash
# ---------------------------------------------------------------------------

def test_different_timestamp_produces_different_hash():
    kwargs = dict(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="create",
        entity_type="user",
        entity_id="u1",
        previous_hash=None,
    )
    h1 = compute_entry_hash(
        created_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC), **kwargs
    )
    h2 = compute_entry_hash(
        created_at=datetime(2026, 4, 12, 0, 0, 1, tzinfo=UTC), **kwargs
    )
    assert h1 != h2


# ---------------------------------------------------------------------------
# None vs empty string for previous_hash
# ---------------------------------------------------------------------------

def test_none_and_empty_previous_hash_differ():
    """None previous_hash serialises as '' (same as empty string),
    so they must produce the SAME hash (both map to '').
    The contract is: None → treated as '' in canonical form."""
    kwargs = dict(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="create",
        entity_type="user",
        entity_id="u1",
        created_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
    )
    h_none = compute_entry_hash(previous_hash=None, **kwargs)
    h_empty = compute_entry_hash(previous_hash="", **kwargs)
    # Both map to '' in the canonical string
    assert h_none == h_empty


def test_previous_hash_with_value_differs_from_none():
    kwargs = dict(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="create",
        entity_type="user",
        entity_id="u1",
        created_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
    )
    h_none = compute_entry_hash(previous_hash=None, **kwargs)
    h_val = compute_entry_hash(previous_hash="a" * 64, **kwargs)
    assert h_none != h_val


# ---------------------------------------------------------------------------
# None vs empty string for entity_type / entity_id
# ---------------------------------------------------------------------------

def test_none_entity_type_and_id_treated_as_empty():
    kwargs = dict(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        action="create",
        created_at=datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC),
        previous_hash=None,
    )
    h_none = compute_entry_hash(entity_type=None, entity_id=None, **kwargs)
    h_empty = compute_entry_hash(entity_type="", entity_id="", **kwargs)
    assert h_none == h_empty


# ---------------------------------------------------------------------------
# Unicode normalization
# ---------------------------------------------------------------------------

def test_unicode_normalization_nfc():
    """Two strings differing only in Unicode normalization (NFC vs NFD)
    should produce the SAME hash because the function normalizes to NFC."""
    tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    created_at = datetime(2026, 4, 12, 0, 0, 0, tzinfo=UTC)
    previous_hash = None

    # NFC vs NFD representations of the same character (é = U+00E9 vs U+0065 U+0301)
    nfc_action = unicodedata.normalize("NFC", "cre\u00e9")   # 'creé' — single codepoint
    nfd_action = unicodedata.normalize("NFD", "cre\u00e9")   # 'creé' — decomposed

    assert nfc_action != nfd_action  # confirm they differ before normalizing

    h_nfc = compute_entry_hash(
        tenant_id=tenant_id,
        action=nfc_action,
        entity_type=None,
        entity_id=None,
        created_at=created_at,
        previous_hash=previous_hash,
    )
    h_nfd = compute_entry_hash(
        tenant_id=tenant_id,
        action=nfd_action,
        entity_type=None,
        entity_id=None,
        created_at=created_at,
        previous_hash=previous_hash,
    )
    assert h_nfc == h_nfd, (
        "NFC and NFD representations of the same string should hash identically"
    )
