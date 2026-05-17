"""SP-1 Plan D B4 -- drop journal_entries.entry_hash server_default.

The 0006 migration added entry_hash with `server_default=""` so the existing
backfill loop could insert NOT NULL rows pre-backfill. With the chain
backfilled and the JournalEntry before_insert event listener auto-computing
entry_hash, the default is no longer needed and its presence allows future
direct DB inserts to land an empty (unverifiable) hash. Drop the default
so any insert without an explicit (or auto-computed) hash fails fast.

Revision ID: 0007_journal_entry_hash_drop_default
Revises: 0006_add_journal_hash_chain
Create Date: 2026-05-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_journal_entry_hash_drop_default"
down_revision: Union[str, None] = "0006_add_journal_hash_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "journal_entries",
        "entry_hash",
        server_default=None,
        existing_type=sa.String(64),
        existing_nullable=False,
        schema="billing",
    )


def downgrade() -> None:
    op.alter_column(
        "journal_entries",
        "entry_hash",
        server_default="",
        existing_type=sa.String(64),
        existing_nullable=False,
        schema="billing",
    )
