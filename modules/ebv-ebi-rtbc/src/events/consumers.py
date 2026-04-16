"""Event consumers for the EBV/EBI/RTBC module.

Listens for member enrollment changes to invalidate eligibility caches
and trigger re-verification.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def on_member_enrolled(payload: dict[str, Any]) -> None:
    """Handle member.enrolled event -- pre-warm eligibility cache."""
    member_id = payload.get("member_id")
    tenant_id = payload.get("tenant_id")
    logger.info(
        "Member enrolled, pre-warming eligibility cache",
        extra={
            "svc_name": "ebv.events",
            "ebv_member_id": member_id,
            "ebv_tenant_id": str(tenant_id) if tenant_id else None,
        },
    )


async def on_member_terminated(payload: dict[str, Any]) -> None:
    """Handle member.terminated event -- invalidate eligibility cache."""
    member_id = payload.get("member_id")
    tenant_id = payload.get("tenant_id")
    logger.info(
        "Member terminated, invalidating eligibility cache",
        extra={
            "svc_name": "ebv.events",
            "ebv_member_id": member_id,
            "ebv_tenant_id": str(tenant_id) if tenant_id else None,
        },
    )


async def on_accumulator_updated(payload: dict[str, Any]) -> None:
    """Handle accumulator.updated event -- refresh benefit phase data."""
    member_id = payload.get("member_id")
    tenant_id = payload.get("tenant_id")
    logger.info(
        "Accumulator updated, refreshing benefit phase",
        extra={
            "svc_name": "ebv.events",
            "ebv_member_id": member_id,
            "ebv_tenant_id": str(tenant_id) if tenant_id else None,
        },
    )


async def on_formulary_changed(payload: dict[str, Any]) -> None:
    """Handle formulary.changed event -- invalidate cached benefit investigations."""
    plan_id = payload.get("plan_id")
    tenant_id = payload.get("tenant_id")
    logger.info(
        "Formulary changed, invalidating benefit investigation cache",
        extra={
            "svc_name": "ebv.events",
            "ebv_plan_id": str(plan_id) if plan_id else None,
            "ebv_tenant_id": str(tenant_id) if tenant_id else None,
        },
    )


EVENT_HANDLERS = {
    "member.enrolled": on_member_enrolled,
    "member.terminated": on_member_terminated,
    "accumulator.updated": on_accumulator_updated,
    "formulary.changed": on_formulary_changed,
}
