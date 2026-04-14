"""AS2 (Applicability Statement 2) transport layer for EDI file exchange.

AS2 is the HIPAA-mandated internet transport for X12 EDI.
This module handles:
  - AS2 message building (MIME multipart/signed)
  - MDN (Message Disposition Notification) generation and parsing
  - AS2 identifier management
  - Certificate attachment

Cryptographic operations are delegated to the certificate manager.
No plaintext EDI content is logged at any level.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional


class AS2DispositionType(str, Enum):
    PROCESSED = "processed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class AS2Message:
    """Represents an outbound or inbound AS2 message."""
    message_id: str
    from_id: str
    to_id: str
    content_type: str = "application/edi-x12"
    subject: str = ""
    payload_bytes: bytes = field(default_factory=bytes)
    headers: Dict[str, str] = field(default_factory=dict)
    signed: bool = True
    encrypted: bool = True
    request_mdn: bool = True
    mdn_url: Optional[str] = None


@dataclass
class AS2MDN:
    """Message Disposition Notification — receipt acknowledgment."""
    original_message_id: str
    from_id: str
    to_id: str
    disposition_type: AS2DispositionType
    disposition_modifier: str = ""
    mic: str = ""           # Message Integrity Check (SHA-256/base64)
    mic_algorithm: str = "sha-256"
    timestamp: str = ""
    error_description: str = ""


def build_as2_message(
    from_id: str,
    to_id: str,
    payload: bytes,
    subject: str = "X12 EDI Transmission",
    signed: bool = True,
    encrypted: bool = True,
    request_mdn: bool = True,
    mdn_url: Optional[str] = None,
) -> AS2Message:
    """Build an AS2 message envelope for outbound EDI transmission."""
    message_id = f"<{uuid.uuid4()}@infinityrx>"
    now = datetime.now(timezone.utc)

    headers = {
        "AS2-Version": "1.2",
        "AS2-From": from_id,
        "AS2-To": to_id,
        "Message-ID": message_id,
        "Date": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "Subject": subject,
        "Content-Type": "application/edi-x12",
        "MIME-Version": "1.0",
    }

    if request_mdn:
        headers["Disposition-Notification-To"] = mdn_url or f"https://as2.infinityrx.com/mdn"
        headers["Disposition-Notification-Options"] = (
            f"signed-receipt-micalg=required,sha-256; signed-receipt-protocol=required,pkcs7-signature"
        )

    return AS2Message(
        message_id=message_id,
        from_id=from_id,
        to_id=to_id,
        payload_bytes=payload,
        headers=headers,
        signed=signed,
        encrypted=encrypted,
        request_mdn=request_mdn,
        mdn_url=mdn_url,
        subject=subject,
    )


def compute_mic(payload: bytes, algorithm: str = "sha-256") -> str:
    """Compute Message Integrity Check (MIC) for AS2 MDN."""
    import base64
    if algorithm in ("sha-256", "sha256"):
        digest = hashlib.sha256(payload).digest()
    elif algorithm in ("sha-1", "sha1"):
        digest = hashlib.sha1(payload).digest()  # nosec B303 — required by AS2 spec
    else:
        digest = hashlib.sha256(payload).digest()
    return base64.b64encode(digest).decode("ascii")


def build_mdn(
    original_message: AS2Message,
    success: bool = True,
    error_description: str = "",
) -> AS2MDN:
    """Build an MDN response for a received AS2 message."""
    now = datetime.now(timezone.utc)
    mic = compute_mic(original_message.payload_bytes) if original_message.payload_bytes else ""

    if success:
        disposition_type = AS2DispositionType.PROCESSED
        modifier = ""
    else:
        disposition_type = AS2DispositionType.FAILED
        modifier = "decryption-failed" if not error_description else "processing-error"

    return AS2MDN(
        original_message_id=original_message.message_id,
        from_id=original_message.to_id,     # MDN sent from recipient
        to_id=original_message.from_id,     # back to sender
        disposition_type=disposition_type,
        disposition_modifier=modifier,
        mic=mic,
        mic_algorithm="sha-256",
        timestamp=now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        error_description=error_description,
    )


def parse_mdn(headers: Dict[str, str], body: str) -> AS2MDN:
    """Parse an inbound MDN from HTTP response headers and body."""
    from_id = headers.get("AS2-From", "")
    to_id = headers.get("AS2-To", "")
    original_message_id = headers.get("Original-Message-ID",
                                       headers.get("Message-ID", ""))
    timestamp = headers.get("Date", "")

    disposition_str = ""
    mic = ""
    mic_algorithm = "sha-256"

    for line in body.splitlines():
        lower = line.lower()
        if lower.startswith("disposition:"):
            disposition_str = line.split(":", 1)[1].strip()
        elif lower.startswith("received-content-mic:"):
            parts = line.split(":", 1)[1].strip().split(",")
            mic = parts[0].strip()
            if len(parts) > 1:
                mic_algorithm = parts[1].strip()

    if "processed" in disposition_str.lower():
        disposition_type = AS2DispositionType.PROCESSED
    elif "failed" in disposition_str.lower():
        disposition_type = AS2DispositionType.FAILED
    else:
        disposition_type = AS2DispositionType.ERROR

    modifier_part = ""
    if "/" in disposition_str:
        modifier_part = disposition_str.split("/", 1)[1].strip()

    return AS2MDN(
        original_message_id=original_message_id,
        from_id=from_id,
        to_id=to_id,
        disposition_type=disposition_type,
        disposition_modifier=modifier_part,
        mic=mic,
        mic_algorithm=mic_algorithm,
        timestamp=timestamp,
    )
