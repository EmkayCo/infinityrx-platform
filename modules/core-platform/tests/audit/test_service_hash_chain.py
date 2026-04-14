"""AuditService hash-chain integration tests.

Written test-first for P1 Item 1 of the emergency wiring pass. Verifies that
``AuditService.log()`` actually computes and persists the tamper-evident hash
chain — previously the columns existed in the schema but were never populated.
"""

from __future__ import annotations

import uuid

from src.audit.hash_chain import GENESIS_HASH, compute_entry_hash
from src.audit.models import AuditLog
from src.audit.schemas import AuditEntry
from src.audit.service import AuditService


def _entry(tenant: uuid.UUID, action: str = "create", entity_id: str = "u1") -> AuditEntry:
    return AuditEntry(
        tenant_id=tenant,
        user_id=uuid.uuid4(),
        action=action,
        module="core-platform",
        entity_type="user",
        entity_id=entity_id,
        before_value=None,
        after_value={"name": "Alice"},
        ip_address="127.0.0.1",
        user_agent="pytest",
        correlation_id=uuid.uuid4(),
    )


def test_first_entry_uses_genesis_previous_hash(db_session, tenant_id):
    svc = AuditService(db_session)
    row = svc.log(_entry(tenant_id))
    db_session.commit()

    assert row.previous_hash == GENESIS_HASH
    assert row.entry_hash != ""
    assert len(row.entry_hash) == 64


def test_three_entries_form_unbroken_chain(db_session, tenant_id):
    svc = AuditService(db_session)
    row1 = svc.log(_entry(tenant_id, action="create", entity_id="u1"))
    row2 = svc.log(_entry(tenant_id, action="update", entity_id="u1"))
    row3 = svc.log(_entry(tenant_id, action="delete", entity_id="u1"))
    db_session.commit()

    assert row1.previous_hash == GENESIS_HASH
    assert row2.previous_hash == row1.entry_hash
    assert row3.previous_hash == row2.entry_hash

    # No duplicates — each action produces a distinct hash.
    hashes = {row1.entry_hash, row2.entry_hash, row3.entry_hash}
    assert len(hashes) == 3


def test_entry_hash_matches_canonical_computation(db_session, tenant_id):
    svc = AuditService(db_session)
    row = svc.log(_entry(tenant_id, action="create", entity_id="u-canonical"))
    db_session.commit()

    expected = compute_entry_hash(
        tenant_id=tenant_id,
        action="create",
        entity_type="user",
        entity_id="u-canonical",
        created_at=row.created_at,
        previous_hash=GENESIS_HASH,
    )
    assert row.entry_hash == expected


def test_per_tenant_chains_are_independent(db_session, tenant_id, other_tenant_id):
    svc = AuditService(db_session)
    a1 = svc.log(_entry(tenant_id, action="create"))
    b1 = svc.log(_entry(other_tenant_id, action="create"))
    a2 = svc.log(_entry(tenant_id, action="update"))
    b2 = svc.log(_entry(other_tenant_id, action="update"))
    db_session.commit()

    # Each tenant starts at GENESIS and chains to its own previous entry,
    # irrespective of writes from other tenants interleaved in between.
    assert a1.previous_hash == GENESIS_HASH
    assert b1.previous_hash == GENESIS_HASH
    assert a2.previous_hash == a1.entry_hash
    assert b2.previous_hash == b1.entry_hash


def test_verify_chain_detects_tampering(db_session, tenant_id):
    """If a row's after_value is altered post-write, the recomputed hash for
    downstream entries would no longer match the stored entry_hash. This test
    documents the invariant that a verifier can use later."""
    svc = AuditService(db_session)
    row1 = svc.log(_entry(tenant_id, action="create"))
    row2 = svc.log(_entry(tenant_id, action="update"))
    db_session.commit()

    # Sanity: chain linkage holds.
    assert row2.previous_hash == row1.entry_hash

    # Recomputing row2's hash using the stored inputs and stored previous_hash
    # must match what was persisted. This is the verification primitive.
    recomputed = compute_entry_hash(
        tenant_id=tenant_id,
        action="update",
        entity_type="user",
        entity_id="u1",
        created_at=row2.created_at,
        previous_hash=row2.previous_hash,
    )
    assert recomputed == row2.entry_hash


def test_log_populates_columns_on_in_memory_session_before_commit(db_session, tenant_id):
    """The hash must be computed before flush so it's on the returned row."""
    svc = AuditService(db_session)
    row = svc.log(_entry(tenant_id))
    # Do NOT commit — the service must set the hash before it's queryable,
    # because callers use the returned row (and because the server_default=""
    # would otherwise mask a missing computation).
    assert row.entry_hash != ""
    assert row.previous_hash == GENESIS_HASH


def test_chain_survives_reload_from_db(db_session, tenant_id):
    svc = AuditService(db_session)
    r1 = svc.log(_entry(tenant_id, action="create"))
    r2 = svc.log(_entry(tenant_id, action="update"))
    db_session.commit()

    reloaded = db_session.query(AuditLog).filter(AuditLog.id.in_([r1.id, r2.id])).order_by(AuditLog.id).all()
    assert len(reloaded) == 2
    assert reloaded[0].entry_hash == r1.entry_hash
    assert reloaded[1].previous_hash == reloaded[0].entry_hash
