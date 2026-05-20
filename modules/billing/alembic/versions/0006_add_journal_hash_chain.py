"""SP-1 Plan D Task 3 -- add hash-chain columns to billing.journal_entries.

Adds:
  - entry_hash VARCHAR(64) NOT NULL -- SHA-256 hex of this row's canonical fields
  - prev_hash  VARCHAR(64) NULL     -- SHA-256 hex of the preceding row in the
                                       tenant chain (NULL for the first entry)
  - idx_journal_chain_order(tenant_id, created_at) -- chain ordering index

The columns are added nullable first, backfilled in Python (tenant by tenant,
ordered by created_at ASC, id ASC), then entry_hash is set NOT NULL.

Canonical hash input (pipe-delimited, UTF-8):
  tenant_id | entry_type | amount_quantized | category | reference_type |
  reference_id | created_at_iso | prev_hash_or_empty

Revision ID: 0006_add_journal_hash_chain
Revises: 0005_add_file_artifacts
Create Date: 2026-05-17
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0006_add_journal_hash_chain"
down_revision: Union[str, None] = "0005_add_file_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_TABLE = f"{_SCHEMA}.journal_entries"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


# ---------------------------------------------------------------------------
# Hash helpers (same algorithm used by the verifier service)
# ---------------------------------------------------------------------------

def _canonical_amount(amount) -> str:
    """Quantize to 2dp ROUND_HALF_UP and return as string."""
    d = Decimal(str(amount))
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _naive_utc_iso(dt) -> str:
    """Return a timezone-naive UTC ISO string.

    Stripping tzinfo makes the canonical string identical across SQLite
    (which drops tzinfo on SELECT) and Postgres (which preserves it), so
    hashes computed here match what the verifier recomputes on a live SELECT.
    """
    if dt is None:
        return ""
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat()


def _compute_entry_hash(row, prev_hash: str | None) -> str:
    """SHA-256 of the canonical pipe-delimited representation of *row*.

    Fields included (in order):
      tenant_id, entry_type, amount, category, reference_type,
      reference_id, created_at_iso, prev_hash_or_empty
    """
    ph = prev_hash or ""
    ref_type = row.reference_type or ""
    ref_id = str(row.reference_id) if row.reference_id else ""
    created_iso = _naive_utc_iso(row.created_at)
    canonical = "|".join([
        str(row.tenant_id),
        str(row.entry_type),
        _canonical_amount(row.amount),
        str(row.category),
        ref_type,
        ref_id,
        created_iso,
        ph,
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # 1. Add columns nullable so existing rows don't violate NOT NULL yet.
    op.add_column(
        "journal_entries",
        sa.Column("entry_hash", sa.String(64), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "journal_entries",
        sa.Column("prev_hash", sa.String(64), nullable=True),
        schema=_SCHEMA,
    )

    # 2. Chain-order index for the verifier.
    op.create_index(
        "idx_journal_chain_order",
        "journal_entries",
        ["tenant_id", "created_at"],
        schema=_SCHEMA,
    )

    # 3. Backfill: compute hashes in Python, per tenant, oldest-first.
    bind = op.get_bind()
    meta = sa.MetaData()
    je = sa.Table(
        "journal_entries",
        meta,
        sa.Column("id", pg.UUID(as_uuid=True)),
        sa.Column("tenant_id", pg.UUID(as_uuid=True)),
        sa.Column("entry_type", sa.String),
        sa.Column("amount", sa.Numeric),
        sa.Column("category", sa.String),
        sa.Column("reference_type", sa.String),
        sa.Column("reference_id", pg.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("entry_hash", sa.String(64)),
        sa.Column("prev_hash", sa.String(64)),
        schema=_SCHEMA,
    )

    # Gather distinct tenants that have journal entries.
    tenant_rows = bind.execute(
        sa.select(je.c.tenant_id).distinct()
    ).fetchall()

    for (tenant_id,) in tenant_rows:
        rows = bind.execute(
            sa.select(je).where(je.c.tenant_id == tenant_id).order_by(
                je.c.created_at.asc(), je.c.id.asc()
            )
        ).fetchall()

        prev_hash: str | None = None
        for row in rows:
            h = _compute_entry_hash(row, prev_hash)
            bind.execute(
                sa.update(je)
                .where(je.c.id == row.id)
                .values(entry_hash=h, prev_hash=prev_hash)
            )
            prev_hash = h

    # 4. Set entry_hash NOT NULL now that all rows are backfilled.
    op.alter_column(
        "journal_entries",
        "entry_hash",
        nullable=False,
        schema=_SCHEMA,
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    op.drop_index("idx_journal_chain_order", table_name="journal_entries", schema=_SCHEMA)
    op.drop_column("journal_entries", "prev_hash", schema=_SCHEMA)
    op.drop_column("journal_entries", "entry_hash", schema=_SCHEMA)
