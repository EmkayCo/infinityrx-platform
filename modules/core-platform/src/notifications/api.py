"""Notification HTTP API — current-user scoped list, mark-read, preferences."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from src.notifications.service import NotificationService


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    user_id: str
    notification_type: str
    severity: str
    title: str
    message: str
    link: str | None = None
    read_at: object | None = None
    created_at: object


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    notification_type: str
    email_enabled: bool
    in_app_enabled: bool
    sms_enabled: bool


class PreferenceUpdate(BaseModel):
    notification_type: str
    email_enabled: bool | None = None
    in_app_enabled: bool | None = None
    sms_enabled: bool | None = None


def build_notifications_router(
    *,
    get_session: Callable[..., object],
    current_user_dep: Callable[..., object],
    service_factory: Callable[..., NotificationService],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

    @router.get("", response_model=list[NotificationRead])
    def list_notifications(
        unread_only: bool = Query(default=False),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        session=Depends(get_session),
        current=Depends(current_user_dep),
    ):
        svc = service_factory(session)
        return svc.list(
            tenant_id=current.tenant_id,
            user_id=current.id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )

    @router.put("/read-all")
    def mark_all_read(
        session=Depends(get_session),
        current=Depends(current_user_dep),
    ):
        svc = service_factory(session)
        count = svc.mark_all_as_read(tenant_id=current.tenant_id, user_id=current.id)
        session.commit()
        return {"marked_read": count}

    @router.put("/{notification_id}/read")
    def mark_read(
        notification_id: uuid.UUID,
        session=Depends(get_session),
        current=Depends(current_user_dep),
    ):
        svc = service_factory(session)
        row = svc.mark_as_read(user_id=current.id, notification_id=notification_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        session.commit()
        return NotificationRead.model_validate(row)

    @router.get("/preferences", response_model=list[PreferenceRead])
    def list_preferences(
        session=Depends(get_session),
        current=Depends(current_user_dep),
    ):
        svc = service_factory(session)
        return svc.list_preferences(current.id)

    @router.put("/preferences", response_model=PreferenceRead)
    def update_preference(
        payload: PreferenceUpdate,
        session=Depends(get_session),
        current=Depends(current_user_dep),
    ):
        svc = service_factory(session)
        row = svc.update_preference(
            user_id=current.id,
            notification_type=payload.notification_type,
            email_enabled=payload.email_enabled,
            in_app_enabled=payload.in_app_enabled,
            sms_enabled=payload.sms_enabled,
        )
        session.commit()
        return row

    return router
