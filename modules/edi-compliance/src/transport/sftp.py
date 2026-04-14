"""SFTP transport layer for EDI file exchange.

Manages SFTP connections to trading partner endpoints for file pickup and delivery.
All file content is treated as binary — no logging of EDI payload.

Connection parameters are passed in; credentials never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional


class SftpTransferDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class SftpTransferStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class SftpConfig:
    host: str
    port: int = 22
    username: str = ""
    key_path: Optional[str] = None      # path to private key file
    password: Optional[str] = None      # only if key not available
    outbound_path: str = "/outbound"
    inbound_path: str = "/inbound"
    known_hosts_path: Optional[str] = None
    timeout_seconds: int = 30
    connect_retries: int = 3


@dataclass
class SftpTransferRecord:
    transfer_id: str
    trading_partner_id: str
    direction: SftpTransferDirection
    filename: str
    byte_count: int
    status: SftpTransferStatus
    timestamp: str
    error: str = ""


def build_sftp_filename(
    transaction_type: str,
    sender_id: str,
    isa_control_number: int,
    now: Optional[datetime] = None,
) -> str:
    """Build a standardized SFTP filename for an EDI file.

    Format: {type}_{sender}_{control}_{YYYYMMDDHHMMSS}.edi
    """
    if now is None:
        now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    safe_sender = sender_id.strip().replace(" ", "_")
    return f"{transaction_type}_{safe_sender}_{isa_control_number:09d}_{timestamp}.edi"


def simulate_sftp_transfer(
    config: SftpConfig,
    direction: SftpTransferDirection,
    filename: str,
    payload: bytes,
    trading_partner_id: str,
) -> SftpTransferRecord:
    """Simulate an SFTP file transfer (for test/mock purposes without live connection).

    In production this would use paramiko or asyncssh.
    Returns a transfer record indicating success.
    """
    import uuid
    transfer_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return SftpTransferRecord(
        transfer_id=transfer_id,
        trading_partner_id=trading_partner_id,
        direction=direction,
        filename=filename,
        byte_count=len(payload),
        status=SftpTransferStatus.SUCCESS,
        timestamp=now,
    )


def validate_sftp_config(config: SftpConfig) -> List[str]:
    """Validate SFTP configuration. Returns list of error strings."""
    errors = []
    if not config.host:
        errors.append("host is required")
    if not config.username:
        errors.append("username is required")
    if not config.key_path and not config.password:
        errors.append("either key_path or password is required")
    if config.port < 1 or config.port > 65535:
        errors.append(f"port must be 1–65535, got {config.port}")
    if config.key_path and not os.path.exists(config.key_path):
        errors.append(f"key_path does not exist: {config.key_path}")
    return errors
