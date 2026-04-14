"""Model-level tests for BankHoliday ORM + Alembic migration.

Test groups
-----------
1. SQLite in-memory round-trip (no Postgres needed)
2. Unique-constraint enforcement
3. Field defaults
4. Alembic migration: upgrade creates table, downgrade drops it (Postgres)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models.bank_holidays import BankHoliday

# ---------------------------------------------------------------------------
# SQLite-friendly Base (no Postgres UUID / gen_random_uuid needed in tests)
# ---------------------------------------------------------------------------

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid as _uuid_mod
from datetime import datetime as _dt


class _TestBase(DeclarativeBase):
    pass


class _BankHolidayLocal(_TestBase):
    """SQLite-compatible mirror of BankHoliday for unit tests."""

    __tablename__ = "bank_holidays_test"
    __table_args__ = (
        UniqueConstraint("holiday_date", "country", name="uq_bh_date_country_test"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(_uuid_mod.uuid4())
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    is_federal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_bank_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[_dt] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


@pytest.fixture()
def sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _TestBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# 1. Round-trip tests (SQLite)
# ---------------------------------------------------------------------------


def test_create_and_retrieve(sqlite_session: Session) -> None:
    h = _BankHolidayLocal(
        holiday_date=date(2026, 1, 1),
        name="New Year's Day",
        country="US",
        is_federal=True,
        is_bank_holiday=True,
    )
    sqlite_session.add(h)
    sqlite_session.commit()
    sqlite_session.expire_all()

    row = sqlite_session.get(_BankHolidayLocal, h.id)
    assert row is not None
    assert row.holiday_date == date(2026, 1, 1)
    assert row.name == "New Year's Day"
    assert row.country == "US"
    assert row.is_federal is True
    assert row.is_bank_holiday is True


def test_defaults_applied(sqlite_session: Session) -> None:
    h = _BankHolidayLocal(holiday_date=date(2026, 7, 4), name="Independence Day")
    sqlite_session.add(h)
    sqlite_session.commit()
    sqlite_session.expire_all()

    row = sqlite_session.get(_BankHolidayLocal, h.id)
    assert row is not None
    assert row.country == "US"
    assert row.is_federal is True
    assert row.is_bank_holiday is True
    assert row.created_at is not None


def test_non_bank_holiday_flag(sqlite_session: Session) -> None:
    """is_bank_holiday=False is valid (e.g. federal but markets open)."""
    h = _BankHolidayLocal(
        holiday_date=date(2026, 10, 12),
        name="Columbus Day",
        country="US",
        is_federal=True,
        is_bank_holiday=False,
    )
    sqlite_session.add(h)
    sqlite_session.commit()
    sqlite_session.expire_all()

    row = sqlite_session.get(_BankHolidayLocal, h.id)
    assert row is not None
    assert row.is_bank_holiday is False


def test_multiple_countries_same_date(sqlite_session: Session) -> None:
    """Same date is allowed for different countries."""
    h_us = _BankHolidayLocal(
        holiday_date=date(2026, 12, 25), name="Christmas Day", country="US"
    )
    h_ca = _BankHolidayLocal(
        holiday_date=date(2026, 12, 25), name="Christmas Day", country="CA"
    )
    sqlite_session.add_all([h_us, h_ca])
    sqlite_session.commit()

    rows = sqlite_session.query(_BankHolidayLocal).filter_by(
        holiday_date=date(2026, 12, 25)
    ).all()
    assert len(rows) == 2
    countries = {r.country for r in rows}
    assert countries == {"US", "CA"}


def test_id_is_uuid_string(sqlite_session: Session) -> None:
    h = _BankHolidayLocal(holiday_date=date(2026, 1, 19), name="MLK Day")
    sqlite_session.add(h)
    sqlite_session.commit()
    # must be a parseable UUID string
    parsed = _uuid_mod.UUID(h.id)
    assert parsed.version == 4


def test_name_stores_unicode(sqlite_session: Session) -> None:
    h = _BankHolidayLocal(
        holiday_date=date(2026, 6, 19), name="Juneteenth \u2014 Independence Day"
    )
    sqlite_session.add(h)
    sqlite_session.commit()
    sqlite_session.expire_all()

    row = sqlite_session.get(_BankHolidayLocal, h.id)
    assert row is not None
    assert "\u2014" in row.name


# ---------------------------------------------------------------------------
# 2. Unique constraint tests
# ---------------------------------------------------------------------------


def test_unique_constraint_same_date_country(sqlite_session: Session) -> None:
    h1 = _BankHolidayLocal(
        holiday_date=date(2026, 7, 3), name="Independence Day (Observed)", country="US"
    )
    h2 = _BankHolidayLocal(
        holiday_date=date(2026, 7, 3), name="Duplicate", country="US"
    )
    sqlite_session.add(h1)
    sqlite_session.commit()
    sqlite_session.add(h2)
    with pytest.raises(IntegrityError):
        sqlite_session.commit()


def test_unique_constraint_different_countries_allowed(sqlite_session: Session) -> None:
    h_us = _BankHolidayLocal(
        holiday_date=date(2026, 11, 11), name="Veterans Day", country="US"
    )
    h_gb = _BankHolidayLocal(
        holiday_date=date(2026, 11, 11), name="Remembrance Day", country="GB"
    )
    sqlite_session.add_all([h_us, h_gb])
    sqlite_session.commit()  # must not raise

    count = sqlite_session.query(_BankHolidayLocal).filter_by(
        holiday_date=date(2026, 11, 11)
    ).count()
    assert count == 2


def test_unique_constraint_different_dates_allowed(sqlite_session: Session) -> None:
    h1 = _BankHolidayLocal(
        holiday_date=date(2026, 1, 1), name="New Year's Day", country="US"
    )
    h2 = _BankHolidayLocal(
        holiday_date=date(2026, 1, 2), name="New Year Observed", country="US"
    )
    sqlite_session.add_all([h1, h2])
    sqlite_session.commit()  # must not raise

    count = sqlite_session.query(_BankHolidayLocal).filter_by(country="US").count()
    assert count == 2


# ---------------------------------------------------------------------------
# 3. ORM model class-level tests (no DB needed)
# ---------------------------------------------------------------------------


def test_bank_holiday_tablename() -> None:
    assert BankHoliday.__tablename__ == "bank_holidays"


def test_bank_holiday_schema() -> None:
    args = BankHoliday.__table_args__
    schema_dict = next(a for a in args if isinstance(a, dict))
    assert schema_dict["schema"] == "core"


def test_bank_holiday_unique_constraint_columns() -> None:
    args = BankHoliday.__table_args__
    uc = next(a for a in args if isinstance(a, UniqueConstraint))
    col_names = {c.key for c in uc.columns}
    assert col_names == {"holiday_date", "country"}
    assert uc.name == "uq_bank_holiday_date_country"


def test_bank_holiday_has_required_columns() -> None:
    cols = {c.name for c in BankHoliday.__table__.columns}
    required = {"id", "holiday_date", "name", "country", "is_federal", "is_bank_holiday", "created_at"}
    assert required.issubset(cols)


# ---------------------------------------------------------------------------
# 4. Alembic migration round-trip (Postgres)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "modules" / "core-platform" / "alembic.ini"


def _run_alembic(*args: str) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    import os

    env = {**os.environ, "DATABASE_URL_SYNC": ""}  # force asyncpg path in env.py
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(_ALEMBIC_INI), *args],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.mark.integration
async def test_migration_upgrade_creates_table() -> None:
    """Apply 0002; verify bank_holidays exists in core schema."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from shared.config import get_settings

    result = _run_alembic("upgrade", "0002_bank_holidays")
    assert result.returncode == 0, result.stderr

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text as _text

            res = await conn.execute(
                _text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema='core' AND table_name='bank_holidays'"
                )
            )
            assert res.fetchone() is not None, "bank_holidays table not found after upgrade"

            cols_res = await conn.execute(
                _text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema='core' AND table_name='bank_holidays'"
                )
            )
            cols = {r[0] for r in cols_res.fetchall()}
            assert cols >= {
                "id",
                "holiday_date",
                "name",
                "country",
                "is_federal",
                "is_bank_holiday",
                "created_at",
            }

            uq_res = await conn.execute(
                _text(
                    "SELECT constraint_name FROM information_schema.table_constraints"
                    " WHERE table_schema='core' AND table_name='bank_holidays'"
                    " AND constraint_type='UNIQUE'"
                )
            )
            uq_names = {r[0] for r in uq_res.fetchall()}
            assert "uq_bank_holiday_date_country" in uq_names
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_migration_downgrade_drops_table() -> None:
    """Downgrade back to 0001; verify bank_holidays no longer exists."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from shared.config import get_settings

    # Ensure we are at 0002 first
    _run_alembic("upgrade", "0002_bank_holidays")

    result = _run_alembic("downgrade", "0001_core_baseline")
    assert result.returncode == 0, result.stderr

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text as _text

            res = await conn.execute(
                _text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema='core' AND table_name='bank_holidays'"
                )
            )
            assert res.fetchone() is None, "bank_holidays table still exists after downgrade"
    finally:
        await engine.dispose()
        # Leave DB at 0002 for subsequent tests
        _run_alembic("upgrade", "0002_bank_holidays")
