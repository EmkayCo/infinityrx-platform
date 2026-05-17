"""FileArtifact ORM model -- tracks every generated NACHA / 835 file.

Each row represents one generated file artifact keyed to a PaymentBatch
source.  file_path is stored server-side only and is NEVER returned in
API responses (the download endpoint reads from disk using the stored path).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .tables import BillingBase


class FileArtifact(BillingBase):
    __tablename__ = "file_artifacts"
    __table_args__ = (
        Index("idx_file_artifacts_tenant_generated_at", "tenant_id", "generated_at"),
        Index("idx_file_artifacts_source_batch", "tenant_id", "source_batch_id"),
        Index("idx_file_artifacts_source_payment_run", "tenant_id", "source_payment_run_id"),
        {"schema": "billing"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    # "nacha" | "835"
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    # Exactly one of these two must be non-null (enforced at the service layer).
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.payment_batches.id", ondelete="RESTRICT"), nullable=True
    )
    source_payment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.payment_batches.id", ondelete="RESTRICT"), nullable=True
    )

    # Backward provenance to the Upload that originated the source batch.
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing.uploads.id", ondelete="SET NULL"), nullable=True
    )

    generated_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # Absolute server-side path; NEVER exposed in API responses.
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # "generating" | "ready" | "error"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
