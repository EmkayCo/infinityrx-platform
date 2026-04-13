"""Tests for shared.db.models.phi_mixin.PHIMixin.

Verifies a table that inherits PHIMixin:
    * Stores all five PHI columns as LargeBinary (ciphertext) on disk
    * Round-trips Python strs transparently through ORM reads/writes
    * Persists None as NULL (no encryption of missing values)
    * Encrypts with different ciphertext per write (AES-GCM nonce randomness)
"""

from __future__ import annotations

import base64
import os
import secrets
import uuid
from unittest import mock

import pytest
from sqlalchemy import LargeBinary, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import TypeDecorator

from shared.crypto.keys import get_key_provider
from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.models.phi_mixin import PHIMixin

KEY_V1 = base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture(autouse=True)
def env_provider():
    with mock.patch.dict(
        os.environ,
        {"ENCRYPTION_KEY_ACTIVE": KEY_V1, "ENCRYPTION_KEY_ACTIVE_ID": "v1"},
    ):
        get_key_provider(_reset=True)
        yield
    import shared.crypto.keys as _keys_mod

    _keys_mod._provider_instance = None


class _Base(DeclarativeBase):
    pass


class _PHIModel(_Base, PHIMixin):
    __tablename__ = "phi_test_members"

    id: Mapped[str] = mapped_column(primary_key=True)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Columns exist and have expected types
# ---------------------------------------------------------------------------


def test_mixin_defines_five_phi_columns() -> None:
    cols = {c.name for c in _PHIModel.__table__.columns}
    assert {
        "first_name_encrypted",
        "last_name_encrypted",
        "dob_encrypted",
        "ssn_encrypted",
        "address_encrypted",
    }.issubset(cols)


def test_all_phi_columns_use_encrypted_string() -> None:
    for col_name in (
        "first_name_encrypted",
        "last_name_encrypted",
        "dob_encrypted",
        "ssn_encrypted",
        "address_encrypted",
    ):
        col = _PHIModel.__table__.c[col_name]
        # Type decorator wraps LargeBinary — check both the decorator class
        # and its underlying impl.
        assert isinstance(col.type, EncryptedString), f"{col_name} not EncryptedString"


def test_db_storage_type_is_largebinary() -> None:
    """On the DB side, ciphertext is stored as BLOB/LargeBinary."""
    for col_name in ("first_name_encrypted", "ssn_encrypted", "address_encrypted"):
        col = _PHIModel.__table__.c[col_name]
        # TypeDecorator exposes .impl for the underlying storage type
        assert isinstance(col.type.impl_instance, LargeBinary) or isinstance(
            col.type.impl, type
        ) and issubclass(col.type.impl, LargeBinary)


# ---------------------------------------------------------------------------
# Round-trip persistence
# ---------------------------------------------------------------------------


def test_round_trip_plaintext(session: Session) -> None:
    row = _PHIModel(
        id="m1",
        first_name_encrypted="Jane",
        last_name_encrypted="Doe",
        dob_encrypted="1985-07-14",
        ssn_encrypted="123456789",
        address_encrypted='{"street":"1 Main St","city":"NYC"}',
    )
    session.add(row)
    session.commit()
    session.expire_all()

    loaded = session.get(_PHIModel, "m1")
    assert loaded is not None
    assert loaded.first_name_encrypted == "Jane"
    assert loaded.last_name_encrypted == "Doe"
    assert loaded.dob_encrypted == "1985-07-14"
    assert loaded.ssn_encrypted == "123456789"
    assert '"street":"1 Main St"' in loaded.address_encrypted


def test_none_is_stored_as_null(session: Session) -> None:
    row = _PHIModel(id="m2")
    session.add(row)
    session.commit()
    session.expire_all()

    loaded = session.get(_PHIModel, "m2")
    assert loaded is not None
    assert loaded.first_name_encrypted is None
    assert loaded.dob_encrypted is None
    assert loaded.ssn_encrypted is None


def test_ciphertext_differs_per_write(session: Session) -> None:
    """AES-GCM uses random nonces, so two writes of the same plaintext
    produce different ciphertexts (defence against known-plaintext attack)."""
    row1 = _PHIModel(id="a", ssn_encrypted="111223333")
    row2 = _PHIModel(id="b", ssn_encrypted="111223333")
    session.add_all([row1, row2])
    session.commit()

    # Read the raw bytes directly via the underlying LargeBinary column
    from sqlalchemy import text

    result = session.execute(
        text("SELECT id, ssn_encrypted FROM phi_test_members ORDER BY id")
    ).fetchall()
    ct_a = bytes(result[0][1])
    ct_b = bytes(result[1][1])
    assert ct_a != ct_b
    # Both still decrypt correctly via the ORM
    assert session.get(_PHIModel, "a").ssn_encrypted == "111223333"
    assert session.get(_PHIModel, "b").ssn_encrypted == "111223333"


def test_mixin_columns_all_nullable_by_default() -> None:
    """Mixin columns are nullable so subclasses can tighten as needed."""
    for col_name in (
        "first_name_encrypted",
        "last_name_encrypted",
        "dob_encrypted",
        "ssn_encrypted",
        "address_encrypted",
    ):
        col = _PHIModel.__table__.c[col_name]
        assert col.nullable is True, f"{col_name} should be nullable by default"
