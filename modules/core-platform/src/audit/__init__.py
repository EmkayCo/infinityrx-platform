"""Audit logging, PHI access logging, and audit query/export API.

Public interface:
    from src.audit import (
        AuditService,
        AuditEntry,
        AuditMiddleware,
        auditable,
        phi_access,
        router as audit_router,
    )
"""

from src.audit.decorators import auditable, phi_access
from src.audit.middleware import AuditMiddleware
from src.audit.models import AuditLog
from src.audit.schemas import AuditEntry
from src.audit.service import AuditService

__all__ = [
    "AuditEntry",
    "AuditLog",
    "AuditMiddleware",
    "AuditService",
    "auditable",
    "phi_access",
]
