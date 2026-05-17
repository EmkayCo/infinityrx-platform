"""Unit tests for upload_id FK propagation onto derived billing entities.

Verifies:
- PaymentBatch.upload_id column exists, is nullable, FK to billing.uploads.id
- InvoiceLineItem.upload_id column exists, is nullable, FK to billing.uploads.id
- Carryover model exists with correct fields and TenantScopedMixin-style tenant_id
"""
from __future__ import annotations

import inspect
import uuid

import sqlalchemy as sa
import pytest

from modules.billing.src.models.tables import (
    Carryover,
    InvoiceLineItem,
    PaymentBatch,
)


# ---------------------------------------------------------------------------
# PaymentBatch.upload_id
# ---------------------------------------------------------------------------


def test_payment_batch_has_upload_id_column() -> None:
    """PaymentBatch ORM class must declare an upload_id mapped column."""
    table = PaymentBatch.__table__
    assert "upload_id" in table.c, "PaymentBatch is missing upload_id column"


def test_payment_batch_upload_id_is_nullable() -> None:
    """upload_id on PaymentBatch must be nullable (existing rows have no upload)."""
    col = PaymentBatch.__table__.c["upload_id"]
    assert col.nullable, "PaymentBatch.upload_id must be nullable"


def test_payment_batch_upload_id_fk_to_uploads() -> None:
    """PaymentBatch.upload_id must have a FK referencing billing.uploads.id."""
    col = PaymentBatch.__table__.c["upload_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "billing.uploads.id" in fk_targets, (
        f"PaymentBatch.upload_id FK targets {fk_targets!r}, expected billing.uploads.id"
    )


def test_payment_batch_upload_id_is_uuid_type() -> None:
    """upload_id column should store a UUID (Python uuid.UUID)."""
    col = PaymentBatch.__table__.c["upload_id"]
    # The Python-side type is UUID or a compatible dialect type
    assert "UUID" in type(col.type).__name__.upper() or "CHAR" in type(col.type).__name__.upper(), (
        f"Unexpected column type {col.type!r} for PaymentBatch.upload_id"
    )


# ---------------------------------------------------------------------------
# InvoiceLineItem.upload_id
# ---------------------------------------------------------------------------


def test_invoice_line_item_has_upload_id_column() -> None:
    """InvoiceLineItem ORM class must declare an upload_id mapped column."""
    table = InvoiceLineItem.__table__
    assert "upload_id" in table.c, "InvoiceLineItem is missing upload_id column"


def test_invoice_line_item_upload_id_is_nullable() -> None:
    """upload_id on InvoiceLineItem must be nullable."""
    col = InvoiceLineItem.__table__.c["upload_id"]
    assert col.nullable, "InvoiceLineItem.upload_id must be nullable"


def test_invoice_line_item_upload_id_fk_to_uploads() -> None:
    """InvoiceLineItem.upload_id must have a FK referencing billing.uploads.id."""
    col = InvoiceLineItem.__table__.c["upload_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "billing.uploads.id" in fk_targets, (
        f"InvoiceLineItem.upload_id FK targets {fk_targets!r}, expected billing.uploads.id"
    )


def test_invoice_line_item_upload_id_is_uuid_type() -> None:
    """upload_id column should store a UUID."""
    col = InvoiceLineItem.__table__.c["upload_id"]
    assert "UUID" in type(col.type).__name__.upper() or "CHAR" in type(col.type).__name__.upper(), (
        f"Unexpected column type {col.type!r} for InvoiceLineItem.upload_id"
    )


# ---------------------------------------------------------------------------
# Carryover model
# ---------------------------------------------------------------------------


def test_carryover_model_exists() -> None:
    """Carryover ORM class must be importable from billing tables."""
    assert Carryover is not None


def test_carryover_has_id_column() -> None:
    """Carryover must have a primary key id column."""
    table = Carryover.__table__
    assert "id" in table.c, "Carryover missing id column"
    assert table.c["id"].primary_key, "Carryover.id must be primary key"


def test_carryover_has_tenant_id_column() -> None:
    """Carryover must be tenant-scoped (has tenant_id column, not nullable)."""
    table = Carryover.__table__
    assert "tenant_id" in table.c, "Carryover missing tenant_id column"
    col = table.c["tenant_id"]
    assert not col.nullable, "Carryover.tenant_id must not be nullable"


def test_carryover_has_upload_id_column() -> None:
    """Carryover must have upload_id FK column."""
    table = Carryover.__table__
    assert "upload_id" in table.c, "Carryover missing upload_id column"


def test_carryover_upload_id_is_nullable() -> None:
    """Carryover.upload_id must be nullable (legacy rows have no upload)."""
    col = Carryover.__table__.c["upload_id"]
    assert col.nullable, "Carryover.upload_id must be nullable"


def test_carryover_upload_id_fk_to_uploads() -> None:
    """Carryover.upload_id must reference billing.uploads.id."""
    col = Carryover.__table__.c["upload_id"]
    fk_targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "billing.uploads.id" in fk_targets, (
        f"Carryover.upload_id FK targets {fk_targets!r}, expected billing.uploads.id"
    )


def test_carryover_has_ap_record_id_column() -> None:
    """Carryover must reference the source APRecord."""
    table = Carryover.__table__
    assert "ap_record_id" in table.c, "Carryover missing ap_record_id column"


def test_carryover_has_amount_column() -> None:
    """Carryover must have a Decimal amount column."""
    table = Carryover.__table__
    assert "amount" in table.c, "Carryover missing amount column"
    col = table.c["amount"]
    assert "NUMERIC" in type(col.type).__name__.upper() or "DECIMAL" in type(col.type).__name__.upper(), (
        f"Carryover.amount must be Numeric, got {col.type!r}"
    )


def test_carryover_has_reason_column() -> None:
    """Carryover must have a reason/carryover_reason column."""
    table = Carryover.__table__
    assert "reason" in table.c, "Carryover missing reason column"


def test_carryover_has_created_at_column() -> None:
    """Carryover must have a created_at timestamp."""
    table = Carryover.__table__
    assert "created_at" in table.c, "Carryover missing created_at column"


def test_carryover_schema_is_billing() -> None:
    """Carryover table must declare the billing schema in __table_args__.

    We read __table_args__ directly rather than __table__.schema because the
    conftest SQLite fixture nulls out table.schema for all BillingBase tables
    to work around SQLite's lack of schema support. __table_args__ is the
    source of truth -- it is never mutated by fixture setup.
    """
    # __table_args__ is a tuple ending with a dict of keyword args.
    kw = next(
        (item for item in Carryover.__table_args__ if isinstance(item, dict)),
        {},
    )
    schema = kw.get("schema")
    assert schema == "billing", f"Carryover __table_args__ schema is {schema!r}, expected 'billing'"
