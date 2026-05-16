from __future__ import annotations


from src.files import api as files_api
from src.files.storage import LocalStorageBackend


def test_upload_and_download_via_api(client, tenant_admin_a):
    files = {"upload": ("note.txt", b"hello world", "text/plain")}
    resp = client.post("/api/v1/files/upload", files=files)
    assert resp.status_code == 201, resp.text
    fid = resp.json()["id"]

    dl = client.get(f"/api/v1/files/{fid}")
    assert dl.status_code == 200
    assert dl.content == b"hello world"
    assert "note.txt" in dl.headers.get("content-disposition", "")


def test_upload_oversize(client, tenant_admin_a, monkeypatch, tmp_path):
    # shrink backend via new service params by monkeypatching settings
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "MAX_UPLOAD_BYTES", 5)
    files = {"upload": ("a.txt", b"x" * 100, "text/plain")}
    resp = client.post("/api/v1/files/upload", files=files)
    assert resp.status_code == 413


def test_upload_wrong_content_type(client, tenant_admin_a):
    files = {"upload": ("virus.exe", b"x", "application/x-msdownload")}
    resp = client.post("/api/v1/files/upload", files=files)
    assert resp.status_code == 415


def test_list_files(client, tenant_admin_a):
    client.post("/api/v1/files/upload", files={"upload": ("a.txt", b"a", "text/plain")}, data={"module": "m1"})
    client.post("/api/v1/files/upload", files={"upload": ("b.txt", b"b", "text/plain")}, data={"module": "m2"})
    all_ = client.get("/api/v1/files").json()
    assert len(all_) == 2
    m1 = client.get("/api/v1/files?module=m1").json()
    assert len(m1) == 1


def test_download_not_found(client, tenant_admin_a):
    assert client.get("/api/v1/files/nosuch").status_code == 404


def test_delete_file(client, tenant_admin_a):
    up = client.post("/api/v1/files/upload", files={"upload": ("a.txt", b"a", "text/plain")}).json()
    resp = client.delete(f"/api/v1/files/{up['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/files/{up['id']}").status_code == 404


def test_delete_not_found(client, tenant_admin_a):
    assert client.delete("/api/v1/files/nosuch").status_code == 404


def test_tenant_isolation_files(client, tenant_admin_a):
    up = client.post("/api/v1/files/upload", files={"upload": ("a.txt", b"a", "text/plain")}).json()

    from src._shim import auth as auth_shim
    import uuid as _uuid

    auth_shim.set_current_user(
        auth_shim.CurrentUser(
            id=_uuid.uuid4(),
            tenant_id=_uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="b@example.com",
            status="active",
            roles=("tenant_admin",),
        )
    )
    lst_b = client.get("/api/v1/files").json()
    assert lst_b == []
    assert client.get(f"/api/v1/files/{up['id']}").status_code == 404
    assert client.delete(f"/api/v1/files/{up['id']}").status_code == 404


def test_operator_can_upload_but_not_delete(client, tenant_operator_a):
    up = client.post("/api/v1/files/upload", files={"upload": ("a.txt", b"a", "text/plain")})
    assert up.status_code == 201
    assert client.delete(f"/api/v1/files/{up.json()['id']}").status_code == 403


def test_get_backend_singleton_instantiates(tmp_path, monkeypatch):
    # exercise the lazy instantiation branch (reset first)
    files_api.set_backend(None)  # type: ignore[arg-type]
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "lazy"))
    from src._shim import config as cfg

    monkeypatch.setattr(cfg.settings, "STORAGE_LOCAL_PATH", str(tmp_path / "lazy"))
    backend = files_api._get_backend()
    assert isinstance(backend, LocalStorageBackend)
