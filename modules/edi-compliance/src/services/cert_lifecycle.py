"""Certificate lifecycle management for EDI/AS2 transport.

Tracks X.509 certificates used for AS2 encryption/signing.
Manages expiry detection, renewal alerts, and status transitions.
No certificate material is logged at any level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CertStatus(str, Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"   # within alert threshold
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"               # issued but not yet valid


class CertUsage(str, Enum):
    AS2_SIGNING = "as2_signing"
    AS2_ENCRYPTION = "as2_encryption"
    TLS_CLIENT = "tls_client"
    TLS_SERVER = "tls_server"


@dataclass
class CertRecord:
    cert_id: str
    trading_partner_id: str
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    usage: CertUsage
    status: CertStatus = CertStatus.ACTIVE
    fingerprint_sha256: str = ""      # hex digest — not the cert material
    notes: str = ""
    renewed_by_cert_id: Optional[str] = None


@dataclass
class CertAlert:
    cert_id: str
    trading_partner_id: str
    subject: str
    days_until_expiry: int
    not_after: datetime
    usage: CertUsage
    alert_level: str   # "warning" | "critical"


@dataclass
class CertLifecycleReport:
    generated_at: str
    total_certs: int
    active_count: int
    expiring_soon_count: int
    expired_count: int
    revoked_count: int
    alerts: List[CertAlert] = field(default_factory=list)


_DEFAULT_WARN_DAYS = 30
_DEFAULT_CRITICAL_DAYS = 7


def evaluate_cert_status(
    cert: CertRecord,
    now: Optional[datetime] = None,
    warn_days: int = _DEFAULT_WARN_DAYS,
    critical_days: int = _DEFAULT_CRITICAL_DAYS,
) -> CertStatus:
    """Compute current status for a certificate based on validity window."""
    if now is None:
        now = datetime.now(timezone.utc)

    if cert.status == CertStatus.REVOKED:
        return CertStatus.REVOKED

    if now < cert.not_before:
        return CertStatus.PENDING

    if now > cert.not_after:
        return CertStatus.EXPIRED

    days_left = (cert.not_after - now).days
    if days_left <= warn_days:
        return CertStatus.EXPIRING_SOON

    return CertStatus.ACTIVE


def compute_days_until_expiry(cert: CertRecord, now: Optional[datetime] = None) -> int:
    """Return days until certificate expires (negative if already expired)."""
    if now is None:
        now = datetime.now(timezone.utc)
    delta = cert.not_after - now
    return delta.days


def build_cert_alerts(
    certs: List[CertRecord],
    now: Optional[datetime] = None,
    warn_days: int = _DEFAULT_WARN_DAYS,
    critical_days: int = _DEFAULT_CRITICAL_DAYS,
) -> List[CertAlert]:
    """Build alert list for certificates approaching expiry or already expired."""
    if now is None:
        now = datetime.now(timezone.utc)

    alerts: List[CertAlert] = []
    for cert in certs:
        if cert.status == CertStatus.REVOKED:
            continue
        days_left = compute_days_until_expiry(cert, now)
        if days_left <= warn_days:
            alert_level = "critical" if days_left <= critical_days else "warning"
            alerts.append(CertAlert(
                cert_id=cert.cert_id,
                trading_partner_id=cert.trading_partner_id,
                subject=cert.subject,
                days_until_expiry=days_left,
                not_after=cert.not_after,
                usage=cert.usage,
                alert_level=alert_level,
            ))

    alerts.sort(key=lambda a: a.days_until_expiry)
    return alerts


def generate_lifecycle_report(
    certs: List[CertRecord],
    now: Optional[datetime] = None,
    warn_days: int = _DEFAULT_WARN_DAYS,
    critical_days: int = _DEFAULT_CRITICAL_DAYS,
) -> CertLifecycleReport:
    """Generate a full lifecycle report for all tracked certificates."""
    if now is None:
        now = datetime.now(timezone.utc)

    updated: List[CertRecord] = []
    for cert in certs:
        cert.status = evaluate_cert_status(cert, now, warn_days, critical_days)
        updated.append(cert)

    active = sum(1 for c in updated if c.status == CertStatus.ACTIVE)
    expiring = sum(1 for c in updated if c.status == CertStatus.EXPIRING_SOON)
    expired = sum(1 for c in updated if c.status == CertStatus.EXPIRED)
    revoked = sum(1 for c in updated if c.status == CertStatus.REVOKED)

    alerts = build_cert_alerts(updated, now, warn_days, critical_days)

    return CertLifecycleReport(
        generated_at=now.strftime("%Y%m%dT%H%M%SZ"),
        total_certs=len(updated),
        active_count=active,
        expiring_soon_count=expiring,
        expired_count=expired,
        revoked_count=revoked,
        alerts=alerts,
    )


def revoke_cert(cert: CertRecord, reason: str = "") -> CertRecord:
    """Mark a certificate as revoked. Returns updated record."""
    cert.status = CertStatus.REVOKED
    if reason:
        cert.notes = f"REVOKED: {reason}"
    return cert


def renew_cert(
    old_cert: CertRecord,
    new_cert_id: str,
    new_not_before: datetime,
    new_not_after: datetime,
    new_fingerprint: str = "",
) -> CertRecord:
    """Create a renewal record derived from an existing certificate."""
    old_cert.renewed_by_cert_id = new_cert_id
    return CertRecord(
        cert_id=new_cert_id,
        trading_partner_id=old_cert.trading_partner_id,
        subject=old_cert.subject,
        issuer=old_cert.issuer,
        serial_number="",
        not_before=new_not_before,
        not_after=new_not_after,
        usage=old_cert.usage,
        status=CertStatus.PENDING,
        fingerprint_sha256=new_fingerprint,
    )


def parse_cert_metadata(cert_dict: Dict[str, Any]) -> CertRecord:
    """Parse a certificate metadata dict into a CertRecord.

    Expected keys: cert_id, trading_partner_id, subject, issuer,
    serial_number, not_before (ISO str), not_after (ISO str), usage.
    """
    def _parse_dt(val: Any) -> datetime:
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    usage_str = cert_dict.get("usage", "as2_signing")
    try:
        usage = CertUsage(usage_str)
    except ValueError:
        usage = CertUsage.AS2_SIGNING

    return CertRecord(
        cert_id=str(cert_dict.get("cert_id", "")),
        trading_partner_id=str(cert_dict.get("trading_partner_id", "")),
        subject=str(cert_dict.get("subject", "")),
        issuer=str(cert_dict.get("issuer", "")),
        serial_number=str(cert_dict.get("serial_number", "")),
        not_before=_parse_dt(cert_dict.get("not_before", datetime.now(timezone.utc))),
        not_after=_parse_dt(cert_dict.get("not_after", datetime.now(timezone.utc) + timedelta(days=365))),
        usage=usage,
        fingerprint_sha256=str(cert_dict.get("fingerprint_sha256", "")),
    )
