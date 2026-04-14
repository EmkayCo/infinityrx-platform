"""Tests for shared.crypto.sqlalchemy_types — EncryptedString and EncryptedJSON."""

import base64
import os
import secrets
from unittest import mock

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from shared.crypto.aes import DecryptionError
from shared.crypto.keys import get_key_provider
from shared.crypto.sqlalchemy_types import EncryptedJSON, EncryptedString

# ---------------------------------------------------------------------------
# Provider setup
# ---------------------------------------------------------------------------

KEY_V1 = base64.b64encode(secrets.token_bytes(32)).decode()
KEY_V2 = base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture(autouse=True)
def env_provider():
    with mock.patch.dict(
        os.environ,
        {
            "ENCRYPTION_KEY_ACTIVE": KEY_V1,
            "ENCRYPTION_KEY_ACTIVE_ID": "v1",
        },
    ):
        get_key_provider(_reset=True)
        yield
    # Reset singleton to None so it's re-created fresh next test
    import shared.crypto.keys as _keys_mod
    _keys_mod._provider_instance = None


# ---------------------------------------------------------------------------
# Minimal SQLAlchemy models for testing (in-memory SQLite)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class PersonRow(Base):
    __tablename__ = "person"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(EncryptedString(), nullable=True)
    notes = Column(EncryptedJSON(), nullable=True)
    tenant_id = Column(String(50), nullable=True)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


# ---------------------------------------------------------------------------
# EncryptedString — round-trip
# ---------------------------------------------------------------------------


class TestEncryptedString:
    def test_write_and_read_back_plaintext(self, session):
        row = PersonRow(name="Jane Doe")
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.name == "Jane Doe"

    def test_raw_db_value_is_bytes_not_plaintext(self, session, engine):
        row = PersonRow(name="Top Secret")
        session.add(row)
        session.flush()
        row_id = row.id
        # Read directly via raw SQL to get the stored bytes
        with engine.connect() as conn:
            raw = conn.execute(
                text("SELECT name FROM person WHERE id = :id"), {"id": row_id}
            ).scalar()
        # It should be bytes (blob) in SQLite, not the string "Top Secret"
        assert raw is not None
        assert raw != "Top Secret"
        assert isinstance(raw, (bytes, memoryview))

    def test_none_stored_as_none(self, session):
        row = PersonRow(name=None)
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.name is None

    def test_round_trip_unicode(self, session):
        plaintext = "Ñoño — résumé 日本語"
        row = PersonRow(name=plaintext)
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.name == plaintext

    def test_empty_string_round_trip(self, session):
        row = PersonRow(name="")
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.name == ""


# ---------------------------------------------------------------------------
# EncryptedJSON — round-trip
# ---------------------------------------------------------------------------


class TestEncryptedJSON:
    def test_dict_round_trip(self, session):
        data = {"street": "123 Main St", "city": "Springfield", "zip": "12345"}
        row = PersonRow(notes=data)
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.notes == data

    def test_list_round_trip(self, session):
        data = ["item1", "item2", 42, {"nested": True}]
        row = PersonRow(notes=data)
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.notes == data

    def test_none_stored_as_none(self, session):
        row = PersonRow(notes=None)
        session.add(row)
        session.flush()
        session.expire(row)
        assert row.notes is None

    def test_raw_db_value_is_not_plaintext_json(self, session, engine):
        data = {"ssn": "123-45-6789"}
        row = PersonRow(notes=data)
        session.add(row)
        session.flush()
        row_id = row.id
        with engine.connect() as conn:
            raw = conn.execute(
                text("SELECT notes FROM person WHERE id = :id"), {"id": row_id}
            ).scalar()
        assert raw is not None
        assert "123-45-6789" not in str(raw)


# ---------------------------------------------------------------------------
# memoryview passthrough (simulates PostgreSQL bytea returning memoryview)
# ---------------------------------------------------------------------------


class TestMemoryviewSupport:
    def test_encrypted_string_accepts_memoryview(self):
        """process_result_value should handle memoryview input (PostgreSQL returns these)."""
        import os

        with mock.patch.dict(
            os.environ,
            {"ENCRYPTION_KEY_ACTIVE": KEY_V1, "ENCRYPTION_KEY_ACTIVE_ID": "v1"},
        ):
            get_key_provider(_reset=True)
            col = EncryptedString()
            raw_bytes = col.process_bind_param("memview test", dialect=None)
            mv = memoryview(raw_bytes)
            result = col.process_result_value(mv, dialect=None)
            assert result == "memview test"

    def test_encrypted_json_accepts_memoryview(self):
        import os

        with mock.patch.dict(
            os.environ,
            {"ENCRYPTION_KEY_ACTIVE": KEY_V1, "ENCRYPTION_KEY_ACTIVE_ID": "v1"},
        ):
            get_key_provider(_reset=True)
            col = EncryptedJSON()
            data = {"key": "value"}
            raw_bytes = col.process_bind_param(data, dialect=None)
            mv = memoryview(raw_bytes)
            result = col.process_result_value(mv, dialect=None)
            assert result == data


# ---------------------------------------------------------------------------
# AAD isolation: rows with different tenant_id cannot decrypt each other
# ---------------------------------------------------------------------------


class TestAADIsolation:
    def test_different_aad_cannot_decrypt(self):
        """EncryptedString with explicit AAD: same ciphertext decrypts only with matching AAD."""
        from shared.crypto.aes import decrypt, encrypt

        aad_a = b"tenant:a"
        aad_b = b"tenant:b"

        ct = encrypt(b"sensitive", associated_data=aad_a)
        with pytest.raises(DecryptionError):
            decrypt(ct, associated_data=aad_b)

    def test_same_aad_decrypts_correctly(self):
        from shared.crypto.aes import decrypt, encrypt

        aad = b"tenant:x"
        ct = encrypt(b"value", associated_data=aad)
        assert decrypt(ct, associated_data=aad) == b"value"
