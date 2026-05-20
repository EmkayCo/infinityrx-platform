"""FilesService -- generates NACHA and 835 files and persists FileArtifact rows.

NACHA generation delegates to payment-processing/nacha_generator.py
(generate_nacha_file).  835 generation delegates to
edi-compliance/x12/generators/gen_835.py (generate_835).

The service is intentionally thin: it calls the generators, writes the file
to disk, computes sha256, and inserts a FileArtifact row.  All caller
validation (source exists, kind is valid) happens at the router layer before
the service is invoked.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.models.file_artifact import FileArtifact
from src.models.tables import PaymentBatch

logger = logging.getLogger("billing.services.file_artifact")

_DEFAULT_FILES_DIR = "./data/generated_files"

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _files_dir() -> Path:
    base = Path(os.getenv("PAYSYNC_FILES_DIR", _DEFAULT_FILES_DIR))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_file(path: Path, content: str) -> int:
    """Write text content to path; return byte count."""
    encoded = content.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return len(encoded)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# NACHA generator import (from payment-processing)
# ---------------------------------------------------------------------------

def _import_nacha_generator():
    """Lazy import of generate_nacha_file from payment-processing module.

    The payment-processing module is a sibling service; its src/ is on
    sys.path when running inside the monorepo.  We do a deferred import so
    the billing module still loads cleanly in environments where payment-
    processing is not present (tests mock this function directly).
    """
    pp_src = Path(__file__).resolve().parents[4] / "payment-processing" / "src"
    if str(pp_src) not in sys.path:
        sys.path.insert(0, str(pp_src))
    from services.nacha_generator import (  # type: ignore[import]
        generate_nacha_file,
        NachaFileConfig,
        NachaBatchConfig,
        NachaEntryDetail,
    )
    return generate_nacha_file, NachaFileConfig, NachaBatchConfig, NachaEntryDetail


# ---------------------------------------------------------------------------
# 835 generator import (from edi-compliance)
# ---------------------------------------------------------------------------

def _import_835_generator():
    ec_src = Path(__file__).resolve().parents[4] / "edi-compliance" / "src"
    if str(ec_src) not in sys.path:
        sys.path.insert(0, str(ec_src))
    from x12.generators.gen_835 import generate_835  # type: ignore[import]
    from x12.generators.schemas import Generate835Request  # type: ignore[import]
    return generate_835, Generate835Request


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def generate_nacha(
    *,
    db: Session,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    generated_by: uuid.UUID,
    file_cfg,
    batch_cfg,
    entries: list,
) -> FileArtifact:
    """Generate a NACHA file from a PaymentBatch and persist a FileArtifact row.

    Args:
        db: active SQLAlchemy session
        tenant_id: caller's tenant
        batch_id: PaymentBatch.id (source_batch_id on the artifact)
        generated_by: user UUID from JWT
        file_cfg: NachaFileConfig instance
        batch_cfg: NachaBatchConfig instance
        entries: list[NachaEntryDetail]

    Returns:
        Persisted FileArtifact (status="ready").

    Raises:
        ValueError: propagated from generate_nacha_file on invalid input.
        HTTPException: caller is responsible; service raises ValueError only.
    """
    generate_nacha_file, *_ = _import_nacha_generator()

    result = generate_nacha_file(file_cfg, batch_cfg, entries)

    # Resolve upload_id provenance from the source batch (tenant-scoped per
    # .claude/rules/tenant-isolation.md - cross-tenant batch_id must not leak)
    from sqlalchemy import select as _select  # noqa: PLC0415
    batch: PaymentBatch | None = db.execute(
        _select(PaymentBatch).where(
            PaymentBatch.id == batch_id,
            PaymentBatch.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    upload_id: uuid.UUID | None = batch.upload_id if batch else None

    timestamp = datetime.now(UTC)
    filename = f"nacha_{batch_id}_{timestamp.strftime('%Y%m%dT%H%M%S')}.ach"
    base_dir = _files_dir() / str(tenant_id)
    file_path = base_dir / filename

    byte_count = _write_file(file_path, result.file_content)
    sha256 = _sha256(result.file_content)

    artifact = FileArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind="nacha",
        source_batch_id=batch_id,
        source_payment_run_id=None,
        upload_id=upload_id,
        generated_by=generated_by,
        generated_at=timestamp,
        filename=filename,
        file_path=str(file_path.resolve()),
        file_size=byte_count,
        sha256=sha256,
        status="ready",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "billing.file_artifact.nacha_generated",
        extra={
            "svc_tenant_id": str(tenant_id),
            "svc_artifact_id": str(artifact.id),
            "svc_batch_id": str(batch_id),
            "svc_byte_count": byte_count,
        },
    )
    return artifact


def generate_835(
    *,
    db: Session,
    tenant_id: uuid.UUID,
    source_payment_run_id: uuid.UUID,
    generated_by: uuid.UUID,
    request_835,
) -> FileArtifact:
    """Generate an X12 835 remittance file and persist a FileArtifact row.

    Args:
        db: active SQLAlchemy session
        tenant_id: caller's tenant
        source_payment_run_id: PaymentBatch.id used as the 835 source
        generated_by: user UUID from JWT
        request_835: Generate835Request instance

    Returns:
        Persisted FileArtifact (status="ready").
    """
    gen_835_fn, _ = _import_835_generator()

    file_content: str = gen_835_fn(request_835)

    # Resolve upload_id provenance from the source payment run (tenant-scoped
    # per .claude/rules/tenant-isolation.md - cross-tenant id must not leak)
    from sqlalchemy import select as _select  # noqa: PLC0415
    batch: PaymentBatch | None = db.execute(
        _select(PaymentBatch).where(
            PaymentBatch.id == source_payment_run_id,
            PaymentBatch.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    upload_id: uuid.UUID | None = batch.upload_id if batch else None

    timestamp = datetime.now(UTC)
    filename = f"835_{source_payment_run_id}_{timestamp.strftime('%Y%m%dT%H%M%S')}.835"
    base_dir = _files_dir() / str(tenant_id)
    file_path = base_dir / filename

    byte_count = _write_file(file_path, file_content)
    sha256 = _sha256(file_content)

    artifact = FileArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind="835",
        source_batch_id=None,
        source_payment_run_id=source_payment_run_id,
        upload_id=upload_id,
        generated_by=generated_by,
        generated_at=timestamp,
        filename=filename,
        file_path=str(file_path.resolve()),
        file_size=byte_count,
        sha256=sha256,
        status="ready",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    logger.info(
        "billing.file_artifact.835_generated",
        extra={
            "svc_tenant_id": str(tenant_id),
            "svc_artifact_id": str(artifact.id),
            "svc_payment_run_id": str(source_payment_run_id),
            "svc_byte_count": byte_count,
        },
    )
    return artifact
