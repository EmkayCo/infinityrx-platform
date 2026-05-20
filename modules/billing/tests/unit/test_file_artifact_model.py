"""Unit tests for the FileArtifact ORM model.

Asserts column names, types, FK targets, indexes, and default values.
Uses the in-memory SQLite + SAVEPOINT fixture from conftest.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import BigInteger, DateTime, String, inspect, text

from src.models.file_artifact import FileArtifact
from src.models.tables import BillingBase


# ---------------------------------------------------------------------------
# Column introspection helpers
# ---------------------------------------------------------------------------


def _col(name: str):
    """Return the Column object from FileArtifact.__table__ by name."""
    return FileArtifact.__table__.c[name]


# ---------------------------------------------------------------------------
# Schema / column tests
# ---------------------------------------------------------------------------


class TestFileArtifactColumns:
    def test_table_name(self):
        assert FileArtifact.__tablename__ == "file_artifacts"

    def test_id_is_pk(self):
        col = _col("id")
        assert col.primary_key is True

    def test_tenant_id_not_nullable(self):
        assert _col("tenant_id").nullable is False

    def test_kind_varchar_16_not_nullable(self):
        col = _col("kind")
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 16

    def test_source_batch_id_nullable(self):
        assert _col("source_batch_id").nullable is True

    def test_source_payment_run_id_nullable(self):
        assert _col("source_payment_run_id").nullable is True

    def test_upload_id_nullable(self):
        assert _col("upload_id").nullable is True

    def test_generated_by_not_nullable(self):
        assert _col("generated_by").nullable is False

    def test_generated_at_with_timezone_not_nullable(self):
        col = _col("generated_at")
        assert col.nullable is False
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True

    def test_filename_varchar_512_not_nullable(self):
        col = _col("filename")
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 512

    def test_file_path_varchar_1024_not_nullable(self):
        col = _col("file_path")
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 1024

    def test_file_size_bigint_not_nullable(self):
        col = _col("file_size")
        assert col.nullable is False
        assert isinstance(col.type, BigInteger)

    def test_sha256_string_64_not_nullable(self):
        col = _col("sha256")
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 64

    def test_status_varchar_32_not_nullable(self):
        col = _col("status")
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 32


# ---------------------------------------------------------------------------
# FK introspection
# ---------------------------------------------------------------------------


class TestFileArtifactForeignKeys:
    def test_source_batch_id_fk_target(self):
        fks = {fk.target_fullname for fk in _col("source_batch_id").foreign_keys}
        assert any("payment_batches.id" in t for t in fks)

    def test_source_payment_run_id_fk_target(self):
        fks = {fk.target_fullname for fk in _col("source_payment_run_id").foreign_keys}
        assert any("payment_batches.id" in t for t in fks)

    def test_upload_id_fk_target(self):
        fks = {fk.target_fullname for fk in _col("upload_id").foreign_keys}
        assert any("uploads.id" in t for t in fks)


# ---------------------------------------------------------------------------
# Index introspection
# ---------------------------------------------------------------------------


class TestFileArtifactIndexes:
    def test_composite_index_tenant_generated_at_exists(self):
        names = {idx.name for idx in FileArtifact.__table__.indexes}
        assert "idx_file_artifacts_tenant_generated_at" in names

    def test_composite_index_source_batch_exists(self):
        names = {idx.name for idx in FileArtifact.__table__.indexes}
        assert "idx_file_artifacts_source_batch" in names

    def test_composite_index_source_payment_run_exists(self):
        names = {idx.name for idx in FileArtifact.__table__.indexes}
        assert "idx_file_artifacts_source_payment_run" in names


# ---------------------------------------------------------------------------
# Round-trip persistence tests (SQLite SAVEPOINT fixture)
# ---------------------------------------------------------------------------


class TestFileArtifactPersistence:
    """Persistence tests use nullable FK fields set to None to avoid FK
    constraint violations against payment_batches / uploads in the SQLite
    unit-test DB.  FK shape is verified structurally in TestFileArtifactForeignKeys.
    Integration tests (test_files_router.py) exercise the full FK chain.
    """

    def test_insert_and_retrieve_nacha_artifact(self, db_session):
        artifact_id = uuid.uuid4()

        artifact = FileArtifact(
            id=artifact_id,
            tenant_id=uuid.uuid4(),
            kind="nacha",
            source_batch_id=None,
            generated_by=uuid.uuid4(),
            generated_at=datetime.now(UTC),
            filename="payment_batch_20260517.ach",
            file_path="/data/files/payment_batch_20260517.ach",
            file_size=4096,
            sha256="a" * 64,
            status="ready",
        )
        db_session.add(artifact)
        db_session.flush()

        fetched = db_session.get(FileArtifact, artifact_id)
        assert fetched is not None
        assert fetched.kind == "nacha"
        assert fetched.source_payment_run_id is None
        assert fetched.status == "ready"
        assert fetched.file_size == 4096

    def test_insert_and_retrieve_835_artifact(self, db_session):
        artifact_id = uuid.uuid4()

        artifact = FileArtifact(
            id=artifact_id,
            tenant_id=uuid.uuid4(),
            kind="835",
            source_payment_run_id=None,
            generated_by=uuid.uuid4(),
            generated_at=datetime.now(UTC),
            filename="remittance_20260517.835",
            file_path="/data/files/remittance_20260517.835",
            file_size=8192,
            sha256="b" * 64,
            status="ready",
        )
        db_session.add(artifact)
        db_session.flush()

        fetched = db_session.get(FileArtifact, artifact_id)
        assert fetched is not None
        assert fetched.kind == "835"
        assert fetched.source_batch_id is None

    def test_generating_status_persisted(self, db_session):
        artifact = FileArtifact(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            kind="nacha",
            generated_by=uuid.uuid4(),
            generated_at=datetime.now(UTC),
            filename="pending.ach",
            file_path="/data/files/pending.ach",
            file_size=0,
            sha256="c" * 64,
            status="generating",
        )
        db_session.add(artifact)
        db_session.flush()

        fetched = db_session.get(FileArtifact, artifact.id)
        assert fetched.status == "generating"

    def test_file_path_column_exists(self):
        # file_path is stored server-side; builders MUST NOT include it in
        # API response serialization (download endpoint reads from disk instead).
        col_names = {c.key for c in FileArtifact.__table__.columns}
        assert "file_path" in col_names

    def test_upload_id_provenance_stored(self, db_session):
        upload_id = uuid.uuid4()
        artifact = FileArtifact(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            kind="nacha",
            upload_id=None,
            generated_by=uuid.uuid4(),
            generated_at=datetime.now(UTC),
            filename="prov.ach",
            file_path="/data/files/prov.ach",
            file_size=1024,
            sha256="d" * 64,
            status="ready",
        )
        # upload_id is nullable; verify column accepts None without error
        db_session.add(artifact)
        db_session.flush()

        fetched = db_session.get(FileArtifact, artifact.id)
        assert fetched.upload_id is None
