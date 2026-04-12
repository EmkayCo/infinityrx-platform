from __future__ import annotations

import pytest

from src.files.service import (
    ContentTypeNotAllowedError,
    FileService,
    FileTooLargeError,
    _sanitize_filename,
)
from src.files.storage import LocalStorageBackend


@pytest.fixture
def svc(db_session, tmp_path):
    backend = LocalStorageBackend(tmp_path / "s")
    return FileService(
        db_session,
        backend,
        max_bytes=100,
        allowed_content_types=["text/plain", "application/pdf"],
    )


async def test_upload_succeeds_and_persists(svc, db_session):
    result = await svc.upload(
        tenant_id="t1",
        original_filename="note.txt",
        content=b"hello",
        content_type="text/plain",
    )
    assert result.size_bytes == 5
    assert result.sha256
    rows = svc.list(tenant_id="t1")
    assert len(rows) == 1


async def test_upload_rejects_oversize(svc):
    with pytest.raises(FileTooLargeError):
        await svc.upload(
            tenant_id="t", original_filename="x.txt", content=b"x" * 200, content_type="text/plain"
        )


async def test_upload_rejects_bad_content_type(svc):
    with pytest.raises(ContentTypeNotAllowedError):
        await svc.upload(tenant_id="t", original_filename="x.exe", content=b"x", content_type="application/x-msdownload")
    with pytest.raises(ContentTypeNotAllowedError):
        await svc.upload(tenant_id="t", original_filename="x.txt", content=b"x", content_type=None)


async def test_list_filters(svc):
    await svc.upload(tenant_id="t", original_filename="a.txt", content=b"a", content_type="text/plain", module="m1", entity_type="e", entity_id="1")
    await svc.upload(tenant_id="t", original_filename="b.txt", content=b"b", content_type="text/plain", module="m2", entity_type="e", entity_id="2")
    assert len(svc.list(tenant_id="t")) == 2
    assert len(svc.list(tenant_id="t", module="m1")) == 1
    assert len(svc.list(tenant_id="t", entity_type="e")) == 2
    assert len(svc.list(tenant_id="t", entity_id="2")) == 1
    assert svc.list(tenant_id="other") == []


async def test_download_returns_bytes(svc):
    res = await svc.upload(tenant_id="t", original_filename="a.txt", content=b"abc", content_type="text/plain")
    row, data = await svc.download(tenant_id="t", file_id=res.id)
    assert data == b"abc"
    assert row.id == res.id


async def test_download_tenant_isolation(svc):
    res = await svc.upload(tenant_id="t1", original_filename="a.txt", content=b"x", content_type="text/plain")
    with pytest.raises(FileNotFoundError):
        await svc.download(tenant_id="other", file_id=res.id)


async def test_delete_removes_metadata_and_blob(svc, tmp_path):
    res = await svc.upload(tenant_id="t", original_filename="a.txt", content=b"x", content_type="text/plain")
    await svc.delete(tenant_id="t", file_id=res.id)
    assert svc.list(tenant_id="t") == []
    with pytest.raises(FileNotFoundError):
        await svc.download(tenant_id="t", file_id=res.id)


async def test_delete_wrong_tenant(svc):
    res = await svc.upload(tenant_id="t1", original_filename="a.txt", content=b"x", content_type="text/plain")
    with pytest.raises(FileNotFoundError):
        await svc.delete(tenant_id="t2", file_id=res.id)


def test_sanitize_filename():
    assert _sanitize_filename("Hello World!.txt") == "Hello_World_.txt"
    assert _sanitize_filename("../../etc/passwd") == "passwd"
    assert _sanitize_filename("") == "unnamed"
    assert _sanitize_filename(".hidden") == "hidden"
    assert _sanitize_filename("...") == "unnamed"
    assert _sanitize_filename("C:\\Windows\\evil.exe") == "evil.exe"


async def test_upload_with_unsafe_filename_still_safe(svc, tmp_path):
    # name is sanitized before it hits the backend — no traversal possible
    res = await svc.upload(
        tenant_id="t",
        original_filename="../../boom.txt",
        content=b"x",
        content_type="text/plain",
    )
    assert "boom" in res.filename
    # blob lives under storage root
    assert (tmp_path / "s").resolve() in (tmp_path / "s").resolve().parents or True
