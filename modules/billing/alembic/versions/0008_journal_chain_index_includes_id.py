"""SP-1 Plan D B10-w5 C4 -- add id to chain ordering index for deterministic order.

The original idx_journal_chain_order covered (tenant_id, created_at) only.
Two entries with the same created_at timestamp have non-deterministic order,
which can produce different hash chains on repeated verify-chain runs.
Adding id (UUID, monotonically increasing within a transaction) makes the
ordering fully deterministic.

Revision ID: 0008_journal_chain_index_includes_id
Revises: 0007_journal_entry_hash_drop_default
Create Date: 2026-05-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_journal_chain_index_includes_id"
down_revision: Union[str, None] = "0007_journal_entry_hash_drop_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"


def upgrade() -> None:
    op.drop_index(
        "idx_journal_chain_order",
        table_name="journal_entries",
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_journal_chain_order",
        "journal_entries",
        ["tenant_id", "created_at", "id"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_journal_chain_order",
        table_name="journal_entries",
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_journal_chain_order",
        "journal_entries",
        ["tenant_id", "created_at"],
        schema=_SCHEMA,
    )
