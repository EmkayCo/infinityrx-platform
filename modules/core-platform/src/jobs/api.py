"""REST API for jobs + job runs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim import events as event_bus
from .._shim.auth import CurrentUser, current_user, require_role
from .._shim.db import get_session
from ..models import Job, JobRun
from .registry import JobTypeNotRegistered, default_registry
from .runner import JobRunner
from .scheduler import EVENT_JOB_COMPLETED, EVENT_JOB_FAILED, compute_next_run, validate_cron

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    job_type: str = Field(min_length=1, max_length=100)
    schedule: Optional[str] = Field(default=None, max_length=100)
    config: Optional[Dict[str, Any]] = None
    tenant_scope: bool = True  # False = platform-wide job (requires platform_admin)


class JobUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: Optional[str]
    name: str
    job_type: str
    schedule: Optional[str]
    status: str
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    config: Optional[Dict[str, Any]]


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    items_processed: int
    items_failed: int


def _scope_filter(stmt, user: CurrentUser):
    """Restrict to jobs the user may see.

    Platform admin sees all. Everyone else sees only their tenant's jobs
    (tenant_id matches). Platform-wide (NULL tenant_id) jobs are visible
    to platform_admin only.
    """
    if user.has_role("platform_admin"):
        return stmt
    return stmt.where(Job.tenant_id == str(user.tenant_id))


@router.get("", response_model=List[JobOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def list_jobs(session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> List[JobOut]:
    stmt = _scope_filter(select(Job).order_by(Job.created_at.desc()), user)
    rows = session.execute(stmt).scalars().all()
    return [JobOut.model_validate(r) for r in rows]


@router.post("", response_model=JobOut, status_code=201, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
def create_job(body: JobCreate, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> JobOut:
    if body.schedule and not validate_cron(body.schedule):
        raise HTTPException(status_code=422, detail={"error": "invalid_cron", "schedule": body.schedule})
    if not body.tenant_scope and not user.has_role("platform_admin"):
        raise HTTPException(status_code=403, detail={"error": "platform_scope_requires_platform_admin"})

    tenant_id = None if not body.tenant_scope else str(user.tenant_id)
    job = Job(
        tenant_id=tenant_id,
        name=body.name,
        job_type=body.job_type,
        schedule=body.schedule,
        config=body.config,
        status="active",
        next_run_at=compute_next_run(body.schedule) if body.schedule else None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return JobOut.model_validate(job)


def _load_job_for_user(session: Session, job_id: str, user: CurrentUser) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    if not user.has_role("platform_admin"):
        if job.tenant_id != str(user.tenant_id):
            raise HTTPException(status_code=404, detail={"error": "job_not_found"})
    return job


@router.put("/{job_id}", response_model=JobOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
def update_job(job_id: str, body: JobUpdate, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> JobOut:
    job = _load_job_for_user(session, job_id, user)
    if body.schedule is not None:
        if not validate_cron(body.schedule):
            raise HTTPException(status_code=422, detail={"error": "invalid_cron", "schedule": body.schedule})
        job.schedule = body.schedule
        job.next_run_at = compute_next_run(body.schedule)
    if body.name is not None:
        job.name = body.name
    if body.config is not None:
        job.config = body.config
    if body.status is not None:
        if body.status not in {"active", "paused", "disabled"}:
            raise HTTPException(status_code=422, detail={"error": "invalid_status"})
        job.status = body.status
    session.commit()
    session.refresh(job)
    return JobOut.model_validate(job)


@router.post("/{job_id}/pause", response_model=JobOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
def pause_job(job_id: str, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> JobOut:
    job = _load_job_for_user(session, job_id, user)
    job.status = "paused"
    session.commit()
    session.refresh(job)
    return JobOut.model_validate(job)


@router.post("/{job_id}/run", response_model=JobRunOut, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role("platform_admin", "tenant_admin"))])
async def run_job_now(job_id: str, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> JobRunOut:
    job = _load_job_for_user(session, job_id, user)
    started = datetime.now(timezone.utc)
    run = JobRun(job_id=job.id, status="running", started_at=started)
    session.add(run)
    session.commit()
    session.refresh(run)

    runner = JobRunner(default_registry)
    try:
        result = await runner.run(job_type=job.job_type, payload=dict(job.config or {}))
    except JobTypeNotRegistered as exc:
        result = None
        run.status = "failed"
        run.ended_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        session.commit()
        session.refresh(run)
        event_bus.publish(EVENT_JOB_FAILED, {"job_id": job.id, "job_run_id": run.id, "error_message": str(exc)})
        return JobRunOut.model_validate(run)

    ended = datetime.now(timezone.utc)
    run.status = result.status
    run.ended_at = ended
    run.duration_seconds = int((ended - started).total_seconds())
    run.result = result.result or None
    run.error_message = result.error_message
    run.items_processed = result.items_processed
    run.items_failed = result.items_failed
    job.last_run_at = ended
    session.commit()
    session.refresh(run)
    topic = EVENT_JOB_COMPLETED if result.status == "succeeded" else EVENT_JOB_FAILED
    event_bus.publish(
        topic,
        {
            "job_id": job.id,
            "job_run_id": run.id,
            "status": result.status,
            "error_message": result.error_message,
            "items_processed": result.items_processed,
            "items_failed": result.items_failed,
        },
    )
    return JobRunOut.model_validate(run)


@router.get("/{job_id}/runs", response_model=List[JobRunOut], dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def list_job_runs(job_id: str, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> List[JobRunOut]:
    _load_job_for_user(session, job_id, user)
    rows = session.execute(
        select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc())
    ).scalars().all()
    return [JobRunOut.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=JobRunOut, dependencies=[Depends(require_role("platform_admin", "tenant_admin", "tenant_operator"))])
def get_job_run(run_id: str, session: Session = Depends(get_session), user: CurrentUser = Depends(current_user)) -> JobRunOut:
    run = session.get(JobRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"error": "run_not_found"})
    _load_job_for_user(session, run.job_id, user)
    return JobRunOut.model_validate(run)
