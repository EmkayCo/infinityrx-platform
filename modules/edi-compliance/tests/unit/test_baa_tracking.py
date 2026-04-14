"""H-08: Unit tests for the BAA / TPA tracking service.

Drives the service against an in-memory aiosqlite AsyncSession so the
service's real async SQLAlchemy code paths execute end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.types import TypeDecorator

from shared.db.base import Base
import src.models.edi_models  # noqa: F401 — register tables on Base.metadata
from src.models.edi_models import TradingPartner
from src.services.baa_tracking import (
    AgreementInput,
    InvalidAgreementType,
    check_baa_valid,
    create_agreement,
    get_agreements_by_partner,
    get_expiring_agreements,
)


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


_EDI_TABLES = {
    "trading_partners",
    "trading_partner_agreements",
    "control_number_sequences",
    "transaction_files",
    "transaction_records",
    "compliance_logs",
    "as2_certificates",
    "payer_companion_rules",
}


@pytest_asyncio.fixture(autouse=True)
async def _set_tenant_context():
    """Tenant-scoped queries require an active tenant context (CR-04 wiring).

    When integration tests have run earlier in the suite, install_tenant_loader
    is active on every sync Session — including the sync session backing our
    AsyncSession. The contextvar must be set inside the test's event loop or
    the bindparam in the loader_criteria sees ``None``. An async fixture
    naturally runs in the test task's context.
    """
    from shared.db.tenant_context import set_tenant_context, clear_tenant_context

    token = set_tenant_context(TENANT_ID)
    yield
    clear_tenant_context(token)


@pytest_asyncio.fixture()
async def async_db_session() -> AsyncIterator[AsyncSession]:
    from sqlalchemy import event as _sa_event
    from sqlalchemy.orm import Session as _GlobalSession
    from shared.db.tenant_context import _apply_tenant_filter

    # Earlier integration tests may have installed the tenant loader on the
    # global Session via install_tenant_loader. The loader builds a cached
    # bindparam against an empty tenant context at first call and never
    # refreshes it for our isolated test bus. Detach it for our fixture.
    listener_was_present = False
    if _sa_event.contains(_GlobalSession, "do_orm_execute", _apply_tenant_filter):
        _sa_event.remove(_GlobalSession, "do_orm_execute", _apply_tenant_filter)
        listener_was_present = True


    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            elif isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, INET):
                col.type = String(45)
        table.schema = None

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    edi_metadata_tables = [
        t for t in Base.metadata.tables.values() if t.name in _EDI_TABLES
    ]
    async with engine.begin() as conn:
        for table in edi_metadata_tables:
            await conn.run_sync(table.create)
    # Use a dedicated sync session subclass so install_tenant_loader (which
    # earlier integration tests register on the global Session class) does
    # not intercept our queries with a stale literal_execute bindparam.
    class _IsolatedSync(_SyncSession):
        pass

    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, sync_session_class=_IsolatedSync
    )
    try:
        async with sessionmaker() as session:
            yield session
    finally:
        await engine.dispose()
        if listener_was_present:
            _sa_event.listen(_GlobalSession, "do_orm_execute", _apply_tenant_filter)


@pytest_asyncio.fixture()
async def trading_partner(async_db_session: AsyncSession) -> TradingPartner:
    partner = TradingPartner(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        name="Acme Clearinghouse",
        partner_type="clearinghouse",
        isa_qualifier="ZZ",
        isa_id="ACMECLR",
        gs_id=None,
        supported_transactions=["837P", "835"],
        transport_type="AS2",
        transport_config={},
        test_mode=False,
        is_active=True,
    )
    async_db_session.add(partner)
    await async_db_session.commit()
    return partner


@pytest.mark.asyncio
async def test_create_agreement_persists_baa(async_db_session, trading_partner: TradingPartner) -> None:
    row = await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            executed_date="2026-01-15",
            effective_date="2026-02-01",
            expiry_date="2027-02-01",
            signatory_name="Jane Doe",
            signatory_title="VP Compliance",
        ),
    )
    assert row.agreement_type == "BAA"
    assert row.tenant_id == TENANT_ID
    assert row.trading_partner_id == trading_partner.id
    assert row.expiry_date == "2027-02-01"


@pytest.mark.asyncio
async def test_create_agreement_normalises_lowercase_type(async_db_session, trading_partner: TradingPartner) -> None:
    row = await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="baa",
        ),
    )
    assert row.agreement_type == "BAA"


@pytest.mark.asyncio
async def test_create_agreement_rejects_unknown_type(async_db_session, trading_partner: TradingPartner) -> None:
    with pytest.raises(InvalidAgreementType):
        await create_agreement(
            async_db_session,
            tenant_id=TENANT_ID,
            payload=AgreementInput(
                trading_partner_id=trading_partner.id,
                agreement_type="WHATEVER",
            ),
        )


@pytest.mark.asyncio
async def test_get_agreements_by_partner_returns_all(async_db_session, trading_partner: TradingPartner) -> None:
    for atype in ("BAA", "TPA", "NDA"):
        await create_agreement(
            async_db_session,
            tenant_id=TENANT_ID,
            payload=AgreementInput(
                trading_partner_id=trading_partner.id,
                agreement_type=atype,
                expiry_date="2027-02-01",
            ),
        )
    rows = await get_agreements_by_partner(
        async_db_session, tenant_id=TENANT_ID, trading_partner_id=trading_partner.id
    )
    assert {r.agreement_type for r in rows} == {"BAA", "TPA", "NDA"}


@pytest.mark.asyncio
async def test_get_expiring_agreements_within_window(async_db_session, trading_partner: TradingPartner) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            expiry_date="2026-06-01",  # 48 days away
        ),
    )
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="TPA",
            expiry_date="2027-06-01",  # > 90 days, excluded
        ),
    )
    expiring = await get_expiring_agreements(
        async_db_session, tenant_id=TENANT_ID, days_ahead=90, today=today
    )
    assert len(expiring) == 1
    assert expiring[0].agreement_type == "BAA"


@pytest.mark.asyncio
async def test_get_expiring_agreements_includes_already_expired(
    async_db_session, trading_partner: TradingPartner
) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            expiry_date="2025-12-01",  # already expired
        ),
    )
    expiring = await get_expiring_agreements(
        async_db_session, tenant_id=TENANT_ID, days_ahead=90, today=today
    )
    assert len(expiring) == 1


@pytest.mark.asyncio
async def test_get_expiring_skips_evergreen_agreements(
    async_db_session, trading_partner: TradingPartner
) -> None:
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="NDA",
            expiry_date=None,
        ),
    )
    expiring = await get_expiring_agreements(
        async_db_session, tenant_id=TENANT_ID, days_ahead=365
    )
    assert expiring == []


@pytest.mark.asyncio
async def test_get_expiring_negative_days_raises(async_db_session) -> None:
    with pytest.raises(ValueError):
        await get_expiring_agreements(async_db_session, tenant_id=TENANT_ID, days_ahead=-1)


@pytest.mark.asyncio
async def test_check_baa_valid_returns_true_for_active(async_db_session, trading_partner: TradingPartner) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            effective_date="2026-01-01",
            expiry_date="2027-01-01",
        ),
    )
    assert await check_baa_valid(
        async_db_session,
        tenant_id=TENANT_ID,
        trading_partner_id=trading_partner.id,
        today=today,
    ) is True


@pytest.mark.asyncio
async def test_check_baa_valid_false_when_expired(async_db_session, trading_partner: TradingPartner) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            effective_date="2025-01-01",
            expiry_date="2026-01-01",
        ),
    )
    assert await check_baa_valid(
        async_db_session,
        tenant_id=TENANT_ID,
        trading_partner_id=trading_partner.id,
        today=today,
    ) is False


@pytest.mark.asyncio
async def test_check_baa_valid_false_for_tpa_only(async_db_session, trading_partner: TradingPartner) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="TPA",
            effective_date="2026-01-01",
            expiry_date="2027-01-01",
        ),
    )
    assert await check_baa_valid(
        async_db_session,
        tenant_id=TENANT_ID,
        trading_partner_id=trading_partner.id,
        today=today,
    ) is False


@pytest.mark.asyncio
async def test_check_baa_valid_false_when_not_yet_effective(
    async_db_session, trading_partner: TradingPartner
) -> None:
    today = date(2026, 4, 14)
    await create_agreement(
        async_db_session,
        tenant_id=TENANT_ID,
        payload=AgreementInput(
            trading_partner_id=trading_partner.id,
            agreement_type="BAA",
            effective_date="2027-01-01",
            expiry_date="2028-01-01",
        ),
    )
    assert await check_baa_valid(
        async_db_session,
        tenant_id=TENANT_ID,
        trading_partner_id=trading_partner.id,
        today=today,
    ) is False
