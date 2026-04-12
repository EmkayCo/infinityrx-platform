"""AuditMiddleware — auto-captures every mutating API call.

Responsibilities per PRD 4.3:
    - who: user_id / tenant_id (resolved by a user-provided callable so we
      stay decoupled from T2's auth module while it is being built).
    - what: action derived from HTTP method, module derived from path
      prefix, entity_type/entity_id from ``@auditable`` metadata or path.
    - when: UTC timestamp (SQLAlchemy default).
    - where: client IP (X-Forwarded-For aware) + user agent.
    - before/after: snapshot state via a ``capture_before`` callable
      attached by ``@auditable``. ``after_value`` is read from the response
      body when JSON.
    - correlation_id: taken from ``shared.events.context`` if set, else a
      fresh UUID, and mirrored back on the X-Correlation-ID response header.
    - PHI access logging: emits a second entry for routes decorated with
      ``@phi_access``.
    - Never fails the request — audit write errors are logged and a
      ``audit.write_failed`` event is published.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match, Route
from starlette.types import ASGIApp

from shared.events import (
    EventBus,
    EventEnvelope,
    current_correlation_id,
    event_types,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from src.audit.schemas import AuditEntry
from src.audit.service import AuditService

_logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
METHOD_TO_ACTION = {
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


@dataclass
class AuditContext:
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None


UserResolver = Callable[[Request], Awaitable[AuditContext | None] | AuditContext | None]
SessionFactory = Callable[[], Any]  # yields a sync Session context manager or Session instance


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: SessionFactory,
        user_resolver: UserResolver,
        event_bus: EventBus,
        module_name: str = "core-platform",
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory
        self._user_resolver = user_resolver
        self._event_bus = event_bus
        self._module_name = module_name

    async def dispatch(self, request: Request, call_next):
        # ---- correlation id ----
        incoming = request.headers.get("x-correlation-id")
        token = None
        if incoming:
            try:
                token = set_correlation_id(uuid.UUID(incoming))
            except ValueError:
                token = set_correlation_id(uuid.uuid4())
        elif current_correlation_id() is None:
            new_correlation_id()
            token = None  # generated via contextvar, leave stack alone
        cid = current_correlation_id() or uuid.uuid4()

        # ---- snapshot before for mutating requests that declare capture_before ----
        route_meta = _match_route_meta(request)
        before_value: dict[str, Any] | None = None
        if request.method in MUTATING_METHODS and route_meta is not None:
            capture_before = route_meta.audit.get("capture_before")
            if capture_before is not None:
                try:
                    maybe = capture_before(request)
                    if hasattr(maybe, "__await__"):
                        before_value = await maybe  # type: ignore[assignment]
                    else:
                        before_value = maybe  # type: ignore[assignment]
                except Exception:
                    _logger.exception("audit.capture_before_failed")

        # ---- call downstream ----
        response: Response = await call_next(request)
        response, body_bytes = await _buffer_response(response)

        # Attach correlation id header for every response
        response.headers["X-Correlation-ID"] = str(cid)
        request.state.audit_response_body = body_bytes

        try:
            if request.method in MUTATING_METHODS or (
                route_meta is not None and route_meta.phi_fields
            ):
                await self._write_audit_entries(
                    request=request,
                    response=response,
                    route_meta=route_meta,
                    before_value=before_value,
                    correlation_id=cid,
                )
        except Exception as exc:
            _logger.error("audit.write_failed", extra={"error": str(exc)}, exc_info=True)
            await self._emit_write_failed_event(exc)
        finally:
            if token is not None:
                reset_correlation_id(token)

        return response

    # ------------------------------------------------------------------
    async def _write_audit_entries(
        self,
        *,
        request: Request,
        response: Response,
        route_meta: _RouteMeta | None,
        before_value: dict[str, Any] | None,
        correlation_id: uuid.UUID,
    ) -> None:
        resolved = self._user_resolver(request)
        if hasattr(resolved, "__await__"):
            resolved = await resolved  # type: ignore[assignment]
        if resolved is None:
            return  # unauthenticated requests (e.g., /auth/login) are logged elsewhere

        method_action = METHOD_TO_ACTION.get(request.method, request.method.lower())
        action = method_action
        entity_type: str | None = None
        entity_id: str | None = None
        if route_meta is not None:
            action = route_meta.audit.get("action") or method_action
            entity_type = route_meta.audit.get("entity_type")
            param = route_meta.audit.get("entity_id_param")
            if param and request.path_params.get(param) is not None:
                entity_id = str(request.path_params[param])
        if entity_type is None:
            entity_type = _infer_entity_type(request.url.path)

        after_value = _maybe_parse_json_body(response, getattr(request.state, "audit_response_body", b""))
        ip = _client_ip(request)
        ua = request.headers.get("user-agent")
        module = self._module_name

        session_cm = self._session_factory()
        session = _enter_session(session_cm)
        try:
            svc = AuditService(session)
            if request.method in MUTATING_METHODS:
                svc.log(
                    AuditEntry(
                        tenant_id=resolved.tenant_id,
                        user_id=resolved.user_id,
                        action=action,
                        module=module,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        before_value=before_value,
                        after_value=after_value,
                        ip_address=ip,
                        user_agent=ua,
                        correlation_id=correlation_id,
                    )
                )
            if route_meta is not None and route_meta.phi_fields:
                svc.log(
                    AuditEntry(
                        tenant_id=resolved.tenant_id,
                        user_id=resolved.user_id,
                        action="phi_access",
                        module=module,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        after_value={"fields_accessed": list(route_meta.phi_fields)},
                        ip_address=ip,
                        user_agent=ua,
                        correlation_id=correlation_id,
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            _exit_session(session_cm, session)

    async def _emit_write_failed_event(self, exc: BaseException) -> None:
        try:
            envelope = EventEnvelope(
                event_type=event_types.AUDIT_WRITE_FAILED,
                tenant_id=uuid.UUID(int=0),
                correlation_id=current_correlation_id() or uuid.uuid4(),
                source_module=self._module_name,
                payload={"error": str(exc)},
            )
            await self._event_bus.publish(envelope)
        except Exception:
            _logger.exception("audit.write_failed_event_publish_failed")


# ---------------------------------------------------------------------------
# Route introspection helpers
# ---------------------------------------------------------------------------


@dataclass
class _RouteMeta:
    endpoint: Callable[..., Any]
    audit: dict[str, Any]
    phi_fields: list[str]


def _match_route_meta(request: Request) -> _RouteMeta | None:
    app: FastAPI | None = request.scope.get("app")  # type: ignore[assignment]
    if app is None:
        return None
    for route in app.router.routes:
        if not isinstance(route, Route):
            continue
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            endpoint = route.endpoint
            audit = getattr(endpoint, "__audit__", None) or {}
            phi = getattr(endpoint, "__phi_access__", None) or []
            if audit or phi:
                return _RouteMeta(endpoint=endpoint, audit=audit, phi_fields=phi)
            return _RouteMeta(endpoint=endpoint, audit={}, phi_fields=[])
    return None


def _infer_entity_type(path: str) -> str | None:
    # /api/v1/{module}/{entity_type}/...
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "api":
        return parts[2] if len(parts) >= 3 else None
    if len(parts) >= 1:
        return parts[0]
    return None


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    client = request.client
    return client.host if client else None


def _maybe_parse_json_body(response: Response, body: bytes) -> dict[str, Any] | None:
    if not body:
        return None
    ctype = response.headers.get("content-type", "")
    if "application/json" not in ctype:
        return None
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


async def _buffer_response(response: Response) -> tuple[Response, bytes]:
    """Drain a streaming response body into memory so the audit layer can
    inspect it. Returns a fresh ``Response`` with the same content."""
    body_bytes = b""
    iterator = getattr(response, "body_iterator", None)
    if iterator is not None:
        async for chunk in iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode()
            body_bytes += chunk
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        new_response = Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
        return new_response, body_bytes
    body = getattr(response, "body", b"") or b""
    return response, body


def _enter_session(cm: Any):
    if hasattr(cm, "__enter__"):
        return cm.__enter__()
    return cm


def _exit_session(cm: Any, session: Any) -> None:
    import contextlib

    if hasattr(cm, "__exit__"):
        cm.__exit__(None, None, None)
    else:
        with contextlib.suppress(Exception):
            session.close()
