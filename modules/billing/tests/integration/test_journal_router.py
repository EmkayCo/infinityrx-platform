"""Integration tests for Journal router (SP-1 Plan D Task 3).

Covers:
  - Auth gate (401) -- no token
  - Cross-tenant isolation (403 on X-Tenant-Id mismatch, 404 on wrong-tenant row)
  - Cache-Control: no-store on all responses
  - GET /  returns bare array, tenant-scoped
  - GET /{id} returns 404 for other-tenant rows
  - POST /verify-chain happy path -> verified: true
  - POST /verify-chain tampered entry -> verified: false, broken_at: <id>
  - POST /verify-chain too-large path -> too_large: true
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaab"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
USER_A = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_B = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

APPROVER_A = MagicMock(
    id=USER_A,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("approver",),
    has_role=lambda r: r == "approver",
)
AUDITOR_A = MagicMock(
    id=USER_A,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("auditor",),
    has_role=lambda r: r == "auditor",
)
TENANT_B_USER = MagicMock(
    id=USER_B,
    tenant_id=uuid.UUID(TENANT_B),
    roles=("approver",),
    has_role=lambda r: r == "approver",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in BillingBase.metadata.tables.values():
        table.schema = None
    BillingBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def _session_factory(_engine):
    return sessionmaker(bind=_engine, expire_on_commit=False)


@pytest.fixture()
def _client(_engine, _session_factory):
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_engine)

    def override_db() -> Iterator[Session]:
        session = _session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Hash helpers (mirror journal.py exactly)
# ---------------------------------------------------------------------------


def _canonical_amount(amount) -> str:
    return str(Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _naive_utc_iso(dt) -> str:
    """Mirror the normalization in journal.py and migration 0006."""
    if dt is None:
        return ""
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        from datetime import timezone as _tz
        dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    return dt.isoformat()


def _compute_hash(entry, prev_hash: str | None) -> str:
    ph = prev_hash or ""
    ref_type = entry.reference_type or ""
    ref_id = str(entry.reference_id) if entry.reference_id else ""
    created_iso = _naive_utc_iso(entry.created_at)
    canonical = "|".join([
        str(entry.tenant_id),
        str(entry.entry_type),
        _canonical_amount(entry.amount),
        str(entry.category),
        ref_type,
        ref_id,
        created_iso,
        ph,
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_entry(
    session: Session,
    tenant_id: str,
    *,
    amount: Decimal = Decimal("100.00"),
    entry_type: str = "ap_created",
    category: str = "claims_payable",
    created_at: datetime | None = None,
    entry_hash: str = "",
    prev_hash: str | None = None,
) -> uuid.UUID:
    """Insert a JournalEntry row with caller-supplied hash values and return its id."""
    from src.models.tables import JournalEntry

    now = created_at or datetime.now(UTC)
    eid = uuid.uuid4()
    entry = JournalEntry(
        id=eid,
        tenant_id=uuid.UUID(tenant_id),
        entry_date=date(2026, 1, 15),
        entry_timestamp=now,
        entry_type=entry_type,
        amount=amount,
        category=category,
        description="test journal entry",
        created_at=now,
        entry_hash=entry_hash,
        prev_hash=prev_hash,
    )
    session.add(entry)
    session.commit()
    return eid


def _make_valid_chain(
    session: Session,
    tenant_id: str,
    count: int = 3,
) -> list[uuid.UUID]:
    """Insert `count` journal entries with correct hash chain. Returns list of ids.

    Uses tz-naive UTC datetimes so that SQLite returns them identically on
    SELECT (SQLite drops tzinfo).  _compute_hash uses _naive_utc_iso which
    also strips tzinfo, so hashes computed here match what the verifier sees.
    """
    import types
    from src.models.tables import JournalEntry as _JE

    ids: list[uuid.UUID] = []
    prev: str | None = None

    for i in range(count):
        # Tz-naive: SQLite stores and returns these as-is; no tzinfo drift.
        created_at = datetime(2026, 1, 15, 10 + i, 0, 0)
        eid = uuid.uuid4()

        # Compute hash from a SimpleNamespace matching the same field values.
        row_ns = types.SimpleNamespace(
            tenant_id=uuid.UUID(tenant_id),
            entry_type="ap_created",
            amount=Decimal(f"{(i + 1) * 100}.00"),
            category="claims_payable",
            reference_type=None,
            reference_id=None,
            created_at=created_at,
        )
        h = _compute_hash(row_ns, prev)

        entry = _JE(
            id=eid,
            tenant_id=uuid.UUID(tenant_id),
            entry_date=date(2026, 1, 15),
            entry_timestamp=created_at,
            entry_type="ap_created",
            amount=Decimal(f"{(i + 1) * 100}.00"),
            category="claims_payable",
            description=f"chain entry {i}",
            created_at=created_at,
            entry_hash=h,
            prev_hash=prev,
        )
        session.add(entry)
        session.commit()

        ids.append(eid)
        prev = h

    return ids


# ---------------------------------------------------------------------------
# Auth gate (no token -> 401)
# ---------------------------------------------------------------------------


class TestAuthGate:
    def test_list_no_token_401(self, _client):
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_detail_no_token_401(self, _client):
        resp = _client.get(
            f"/api/v1/billing/journal/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_verify_chain_no_token_401(self, _client):
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cross-tenant isolation (403 on header mismatch)
# ---------------------------------------------------------------------------


class TestCrossTenantHeaderEnforcement:
    def test_list_wrong_tenant_header_403(self, _client):
        """Authenticated as Tenant A but present Tenant B header -> 403."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_verify_chain_wrong_tenant_header_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET / -- list
# ---------------------------------------------------------------------------


class TestListJournalEntries:
    def test_returns_bare_array(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        _make_entry(session, TENANT_A, entry_hash="a" * 64)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_cache_control_no_store(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"

    def test_tenant_scoped_list(self, _client, _session_factory):
        """Tenant A entries must not appear in Tenant B's list."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        _make_entry(session, TENANT_A, entry_hash="b" * 64)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 200
        body = resp.json()
        tenant_a_uuid = str(uuid.UUID(TENANT_A))
        for item in body:
            assert item["tenant_id"] != tenant_a_uuid

    def test_all_roles_can_read(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_A
        resp = _client.get(
            "/api/v1/billing/journal",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /{id} -- detail
# ---------------------------------------------------------------------------


class TestGetJournalEntry:
    def test_returns_entry_for_own_tenant(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        eid = _make_entry(session, TENANT_A, entry_hash="c" * 64)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.get(
            f"/api/v1/billing/journal/{eid}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(eid)
        assert resp.headers.get("cache-control") == "no-store"

    def test_404_for_other_tenant_row(self, _client, _session_factory):
        """Tenant B cannot retrieve Tenant A's entry by id."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        eid = _make_entry(session, TENANT_A, entry_hash="d" * 64)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            f"/api/v1/billing/journal/{eid}",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 404

    def test_404_for_nonexistent_entry(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_A
        resp = _client.get(
            f"/api/v1/billing/journal/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /verify-chain
# ---------------------------------------------------------------------------


class TestVerifyChain:
    def test_happy_path_verified_true(self, _client, _session_factory, monkeypatch):
        """Insert a valid 3-entry chain; verifier should return verified=true."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        # Use a unique tenant so prior test data doesn't interfere.
        chain_tenant = str(uuid.uuid4())
        chain_user = MagicMock(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(chain_tenant),
            roles=("approver",),
            has_role=lambda r: r == "approver",
        )

        session = _session_factory()
        _make_valid_chain(session, chain_tenant, count=3)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: chain_user
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": chain_tenant},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verified"] is True
        assert body["too_large"] is False
        assert body["broken_at"] is None
        assert body["total_entries"] == 3
        assert resp.headers.get("cache-control") == "no-store"

    def test_tampered_entry_returns_verified_false(self, _client, _session_factory, monkeypatch):
        """Tamper with entry_hash of row[1]; verifier should return verified=false."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from sqlalchemy import update
        from src.models.tables import JournalEntry

        chain_tenant = str(uuid.uuid4())
        chain_user = MagicMock(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(chain_tenant),
            roles=("approver",),
            has_role=lambda r: r == "approver",
        )

        session = _session_factory()
        ids = _make_valid_chain(session, chain_tenant, count=3)
        # Tamper: overwrite stored entry_hash of row[1] with garbage.
        session.execute(
            update(JournalEntry)
            .where(JournalEntry.id == ids[1])
            .values(entry_hash="0" * 64)
        )
        session.commit()
        session.close()

        app.dependency_overrides[get_current_user] = lambda: chain_user
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": chain_tenant},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verified"] is False
        assert body["broken_at"] == str(ids[1])

    def test_too_large_returns_verified_null(self, _client, _session_factory, monkeypatch):
        """Insert 3 entries; set SYNC_LIMIT=2 -> too_large=true, verified=null."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        chain_tenant = str(uuid.uuid4())
        chain_user = MagicMock(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(chain_tenant),
            roles=("approver",),
            has_role=lambda r: r == "approver",
        )

        session = _session_factory()
        _make_valid_chain(session, chain_tenant, count=3)
        session.close()

        monkeypatch.setenv("PAYSYNC_HASH_CHAIN_SYNC_LIMIT", "2")

        app.dependency_overrides[get_current_user] = lambda: chain_user
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": chain_tenant},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verified"] is None
        assert body["too_large"] is True
        assert body["total_entries"] == 3
        assert body["broken_at"] is None

    def test_empty_chain_verified_true(self, _client, _session_factory):
        """A tenant with zero entries should verify cleanly."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        empty_tenant = str(uuid.uuid4())
        empty_user = MagicMock(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(empty_tenant),
            roles=("approver",),
            has_role=lambda r: r == "approver",
        )

        app.dependency_overrides[get_current_user] = lambda: empty_user
        resp = _client.post(
            "/api/v1/billing/journal/verify-chain",
            headers={"X-Tenant-Id": empty_tenant},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verified"] is True
        assert body["total_entries"] == 0
        assert body["broken_at"] is None
