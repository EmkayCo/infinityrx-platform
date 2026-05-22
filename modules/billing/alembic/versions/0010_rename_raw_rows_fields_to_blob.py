"""Rename claim_upload_raw_rows.fields -> fields_blob (Stage 1 follow-up).

ORM column was renamed to fields_blob (stores opaque AES-256-GCM ciphertext;
tenant_id bound as AAD in the service layer). Rename the physical column to
match so the live service does not break. No data transform; type unchanged.
"""

from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "0010_rename_raw_rows_fields_to_blob"
down_revision: Union[str, None] = "0009_add_claim_upload_raw_rows"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column(
        "claim_upload_raw_rows", "fields",
        new_column_name="fields_blob", schema="billing",
    )


def downgrade() -> None:
    op.alter_column(
        "claim_upload_raw_rows", "fields_blob",
        new_column_name="fields", schema="billing",
    )
