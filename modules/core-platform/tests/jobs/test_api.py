from __future__ import annotations

from src.jobs.registry import default_registry


async def _noop(_payload):
    return {"items_processed": 1, "items_failed": 0}


def _ensure_handler():
    if "ok" not in default_registry.known_types():
        default_registry.register("ok", _noop)


def test_create_list_and_scope_job(client, tenant_admin_a):
    _ensure_handler()
    resp = client.post(
        "/api/v1/jobs",
        json={"name": "refresh", "job_type": "ok", "schedule": "*/5 * * * *"},
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()
    assert job["tenant_id"] == str(tenant_admin_a.tenant_id)
    assert job["next_run_at"] is not None

    lst = client.get("/api/v1/jobs").json()
    assert any(j["id"] == job["id"] for j in lst)


def test_create_rejects_bad_cron(client, tenant_admin_a):
    _ensure_handler()
    resp = client.post(
        "/api/v1/jobs", json={"name": "x", "job_type": "ok", "schedule": "nope"}
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_cron"


def test_platform_scope_requires_platform_admin(client, tenant_admin_a):
    _ensure_handler()
    resp = client.post(
        "/api/v1/jobs",
        json={"name": "x", "job_type": "ok", "schedule": "* * * * *", "tenant_scope": False},
    )
    assert resp.status_code == 403


def test_update_validates_and_updates_fields(client, tenant_admin_a):
    _ensure_handler()
    job = client.post(
        "/api/v1/jobs", json={"name": "a", "job_type": "ok", "schedule": "* * * * *"}
    ).json()
    resp = client.put(
        f"/api/v1/jobs/{job['id']}",
        json={"name": "b", "schedule": "0 0 * * *", "config": {"k": 1}, "status": "paused"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "b"
    assert resp.json()["status"] == "paused"

    bad = client.put(f"/api/v1/jobs/{job['id']}", json={"schedule": "xx"})
    assert bad.status_code == 422
    bad_status = client.put(f"/api/v1/jobs/{job['id']}", json={"status": "zzz"})
    assert bad_status.status_code == 422


def test_pause_job(client, tenant_admin_a):
    _ensure_handler()
    job = client.post("/api/v1/jobs", json={"name": "a", "job_type": "ok", "schedule": "* * * * *"}).json()
    resp = client.post(f"/api/v1/jobs/{job['id']}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_run_now_success_and_listing(client, tenant_admin_a):
    _ensure_handler()
    job = client.post("/api/v1/jobs", json={"name": "a", "job_type": "ok", "schedule": "* * * * *"}).json()
    resp = client.post(f"/api/v1/jobs/{job['id']}/run")
    assert resp.status_code == 202
    run = resp.json()
    assert run["status"] == "succeeded"

    runs = client.get(f"/api/v1/jobs/{job['id']}/runs").json()
    assert len(runs) == 1
    single = client.get(f"/api/v1/jobs/runs/{run['id']}")
    assert single.status_code == 200


def test_run_now_unregistered(client, tenant_admin_a):
    job = client.post(
        "/api/v1/jobs", json={"name": "z", "job_type": "ghost", "schedule": "* * * * *"}
    ).json()
    resp = client.post(f"/api/v1/jobs/{job['id']}/run")
    assert resp.status_code == 202
    assert resp.json()["status"] == "failed"
    assert "ghost" in (resp.json()["error_message"] or "")


def test_job_not_found(client, tenant_admin_a):
    assert client.put("/api/v1/jobs/nosuch", json={"name": "x"}).status_code == 404
    assert client.post("/api/v1/jobs/nosuch/pause").status_code == 404
    assert client.get("/api/v1/jobs/nosuch/runs").status_code == 404
    assert client.get("/api/v1/jobs/runs/nosuch").status_code == 404


def test_tenant_isolation_jobs(client, tenant_admin_a, app):
    _ensure_handler()
    job_a = client.post(
        "/api/v1/jobs", json={"name": "a", "job_type": "ok", "schedule": "* * * * *"}
    ).json()

    from src._shim import auth as auth_shim
    import uuid as _uuid

    auth_shim.set_current_user(
        auth_shim.CurrentUser(
            id=_uuid.uuid4(),
            tenant_id=_uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="b@example.com",
            roles=["tenant_admin"],
        )
    )
    lst_b = client.get("/api/v1/jobs").json()
    assert all(j["id"] != job_a["id"] for j in lst_b)
    # direct access 404s
    assert client.put(f"/api/v1/jobs/{job_a['id']}", json={"name": "x"}).status_code == 404
    assert client.get(f"/api/v1/jobs/{job_a['id']}/runs").status_code == 404


def test_platform_admin_sees_all(client, platform_admin):
    _ensure_handler()
    # create tenant-scoped job as platform admin
    job = client.post(
        "/api/v1/jobs", json={"name": "p", "job_type": "ok", "schedule": "* * * * *"}
    ).json()
    lst = client.get("/api/v1/jobs").json()
    assert any(j["id"] == job["id"] for j in lst)

    # platform-wide (NULL tenant) job
    plat = client.post(
        "/api/v1/jobs",
        json={"name": "sys", "job_type": "ok", "schedule": "* * * * *", "tenant_scope": False},
    )
    assert plat.status_code == 201
    assert plat.json()["tenant_id"] is None


def test_operator_can_list_but_not_create(client, tenant_operator_a):
    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    create = client.post(
        "/api/v1/jobs", json={"name": "x", "job_type": "ok", "schedule": "* * * * *"}
    )
    assert create.status_code == 403
