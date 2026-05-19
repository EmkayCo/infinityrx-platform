"""Error envelope builder — A3 stub; A4 owns full implementation.

This module provides build_error_envelope() which is first used in Task 3
(transition_investigation_status) and Task 4 (release_hold_v2).
A4 will expand this with typed response models and full error contract.
"""
from __future__ import annotations

import uuid as _uuid


def build_error_envelope(
    code: str,
    message: str,
    *,
    field: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Build a standard error envelope dict.

    Returns a dict matching the error-handling.md contract:
    {"error": {"code": str, "message": str, "field": str|None, "correlation_id": str}}
    """
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "correlation_id": correlation_id or str(_uuid.uuid4()),
        }
    }
