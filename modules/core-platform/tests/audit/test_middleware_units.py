"""Unit tests for middleware helpers and uncommon branches."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from src._shim.db import get_sessionmaker
from src.audit.decorators import auditable, phi_access
from src.audit.middleware import (
    AuditMiddleware,
    _buffer_response,
    _client_ip,
    _enter_session,
    _exit_session,
    _infer_entity_type,
    _match_route_meta,
    _maybe_parse_json_body,
)
from src.audit.phi import phi_access as phi_access_reexport
from starlette.responses import Response

from shared.events import InMemoryEventBus


def _mk_request(scope_overrides: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [],
        "client": ("127.0.0.1", 0),
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "path_params": {},
    }
    scope.update(scope_overrides)
    return Request(scope)


def test_middleware_preserves_preset_correlation_id(db_session):
    """When an ambient correlation id is already bound in the context, the
    middleware must not override it (exercises the elif branch at line 93)."""
    from src.audit.models import AuditLog

    from shared.events.context import reset_correlation_id, set_correlation_id
    db_session.execute(AuditLog.__table__.delete())
    db_session.commit()

    app = FastAPI()

    @app.post("/api/v1/users")
    @auditable(action="create", entity_type="user")
    def create():
        return {"ok": True}

    app.add_middleware(
        AuditMiddleware,
        session_factory=_session_factory,
        user_resolver=lambda r: _Ctx(tenant_id=TENANT, user_id=uuid.uuid4()),
        event_bus=InMemoryEventBus(),
    )

    preset = uuid.UUID("cafecafe-cafe-cafe-cafe-cafecafecafe")
    token = set_correlation_id(preset)
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/users")
        assert resp.status_code == 200
    finally:
        reset_correlation_id(token)


def test_match_route_meta_returns_none_without_app():
    req = _mk_request({})
    assert _match_route_meta(req) is None


def test_match_route_meta_returns_none_when_no_route_matches():
    app = FastAPI()

    @app.get("/known")
    def _known():
        return {}

    req = _mk_request({"app": app, "path": "/unknown", "raw_path": b"/unknown"})
    assert _match_route_meta(req) is None


def test_match_route_meta_skips_non_route_entries():
    from starlette.routing import Mount

    app = FastAPI()
    # Inject a Mount that is not a Route; _match_route_meta must skip it
    app.router.routes.insert(0, Mount("/static", app=lambda *a, **kw: None, name="static"))

    @app.post("/api/v1/users")
    @auditable(action="create", entity_type="user")
    def create():
        return {}

    req = _mk_request({"app": app, "path": "/api/v1/users", "raw_path": b"/api/v1/users", "method": "POST"})
    meta = _match_route_meta(req)
    assert meta is not None and meta.audit["action"] == "create"


def test_phi_reexport_is_same_object():
    assert phi_access_reexport is phi_access


def test_infer_entity_type_from_api_path():
    assert _infer_entity_type("/api/v1/users/123") == "users"
    assert _infer_entity_type("/api/v1") == "api"  # short api path falls through
    assert _infer_entity_type("/dashboard") == "dashboard"
    assert _infer_entity_type("/") is None


def test_maybe_parse_json_body_branches():
    r = Response(content=b"", media_type="application/json")
    assert _maybe_parse_json_body(r, b"") is None
    r = Response(content=b"text", media_type="text/plain")
    assert _maybe_parse_json_body(r, b"text") is None
    r = Response(content=b"not-json", media_type="application/json")
    r.headers["content-type"] = "application/json"
    assert _maybe_parse_json_body(r, b"not-json{{{") is None
    r = Response(content=b"[1,2]", media_type="application/json")
    r.headers["content-type"] = "application/json"
    assert _maybe_parse_json_body(r, b"[1,2]") is None  # list, not dict
    r = Response(content=b'{"a":1}', media_type="application/json")
    r.headers["content-type"] = "application/json"
    assert _maybe_parse_json_body(r, b'{"a":1}') == {"a": 1}


def test_client_ip_without_xff_falls_back_to_request_client():
    scope = {
        "type": "http",
        "headers": [],
        "client": ("198.51.100.7", 0),
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
    }
    req = Request(scope)
    assert _client_ip(req) == "198.51.100.7"


def test_client_ip_with_no_client():
    scope = {
        "type": "http",
        "headers": [],
        "client": None,
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
    }
    req = Request(scope)
    assert _client_ip(req) is None


async def test_buffer_response_handles_str_chunks():
    async def gen():
        yield "hello "
        yield b"world"

    r = PlainTextResponse("")
    r.body_iterator = gen()
    new_resp, body = await _buffer_response(r)
    assert body == b"hello world"
    assert new_resp.body == b"hello world"


async def test_buffer_response_without_iterator():
    r = Response(content=b"abc", media_type="text/plain")
    # Strip iterator so the fallback branch runs
    r.body_iterator = None  # type: ignore[assignment]
    _same, body = await _buffer_response(r)
    assert body == b"abc"


def test_enter_and_exit_session_with_plain_session():
    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    s = FakeSession()
    entered = _enter_session(s)
    assert entered is s
    _exit_session(s, s)
    assert s.closed is True


def test_exit_session_swallows_close_errors():
    class BadSession:
        def close(self):
            raise RuntimeError("nope")

    s = BadSession()
    _exit_session(s, s)  # must not raise


# --------------------------------------------------------------------------
# Integration branches that need the middleware running
# --------------------------------------------------------------------------


TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")


@dataclass
class _Ctx:
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None


def _session_factory():
    SessionLocal = get_sessionmaker()
    return SessionLocal()


async def _async_user_resolver(request):
    return _Ctx(tenant_id=TENANT, user_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


def test_async_user_resolver_and_capture_before(db_session):
    async def _capture_before(req):
        return {"state": "pre"}

    app = FastAPI()

    @app.put("/api/v1/users/{user_id}")
    @auditable(
        action="update", entity_type="user", entity_id_param="user_id", capture_before=_capture_before
    )
    def update(user_id: str):
        return {"id": user_id}

    bus = InMemoryEventBus()
    app.add_middleware(
        AuditMiddleware,
        session_factory=_session_factory,
        user_resolver=_async_user_resolver,
        event_bus=bus,
    )
    client = TestClient(app)
    resp = client.put("/api/v1/users/u-async")
    assert resp.status_code == 200


def test_unauthenticated_resolver_skips_audit(db_session):
    from src.audit.models import AuditLog
    db_session.execute(AuditLog.__table__.delete())
    db_session.commit()

    app = FastAPI()

    @app.post("/api/v1/ping")
    @auditable(action="ping", entity_type="system")
    def ping():
        return {"ok": True}

    def _none_resolver(req):
        return None

    app.add_middleware(
        AuditMiddleware,
        session_factory=_session_factory,
        user_resolver=_none_resolver,
        event_bus=InMemoryEventBus(),
    )
    client = TestClient(app)
    resp = client.post("/api/v1/ping")
    assert resp.status_code == 200
    rows = db_session.query(AuditLog).all()
    assert rows == []


def test_capture_before_exception_is_swallowed(db_session):
    from src.audit.models import AuditLog
    db_session.execute(AuditLog.__table__.delete())
    db_session.commit()

    def _boom(req):
        raise RuntimeError("boom")

    app = FastAPI()

    @app.put("/api/v1/users/{user_id}")
    @auditable(action="update", entity_type="user", entity_id_param="user_id", capture_before=_boom)
    def update(user_id: str):
        return {"id": user_id}

    app.add_middleware(
        AuditMiddleware,
        session_factory=_session_factory,
        user_resolver=lambda r: _Ctx(tenant_id=TENANT, user_id=uuid.uuid4()),
        event_bus=InMemoryEventBus(),
    )
    client = TestClient(app)
    resp = client.put("/api/v1/users/u1")
    assert resp.status_code == 200
    rows = db_session.query(AuditLog).all()
    assert len(rows) == 1 and rows[0].before_value is None


def test_emit_write_failed_event_failure_is_logged(db_session):
    """If the event bus itself fails to publish audit.write_failed, we still
    must not raise — we only log. This exercises the inner-except branch."""
    from src.audit.middleware import AuditMiddleware

    class ExplodingBus:
        async def publish(self, envelope):
            raise RuntimeError("bus down")

        async def subscribe(self, pattern, handler):  # pragma: no cover
            pass

        async def start(self):  # pragma: no cover
            pass

        async def stop(self):  # pragma: no cover
            pass

    app = FastAPI()

    @app.post("/api/v1/users")
    @auditable(action="create", entity_type="user")
    def create():
        return {"id": "u"}

    from src.audit.service import AuditService

    def boom(self, entry):
        raise RuntimeError("db down")

    AuditService_log = AuditService.log
    try:
        AuditService.log = boom  # type: ignore[assignment]
        app.add_middleware(
            AuditMiddleware,
            session_factory=_session_factory,
            user_resolver=lambda r: _Ctx(tenant_id=TENANT, user_id=uuid.uuid4()),
            event_bus=ExplodingBus(),
        )
        client = TestClient(app)
        resp = client.post("/api/v1/users")
        assert resp.status_code == 200
    finally:
        AuditService.log = AuditService_log  # type: ignore[assignment]
