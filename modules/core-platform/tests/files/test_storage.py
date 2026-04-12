from __future__ import annotations

import pytest

from src.files.storage import LocalStorageBackend, StorageBackend, UnsafePathError


async def test_local_backend_put_get_exists_delete(tmp_path):
    be = LocalStorageBackend(tmp_path / "s")
    assert await be.exists("tenant/a.txt") is False
    uri = await be.put("tenant/a.txt", b"hello")
    assert uri.endswith("a.txt")
    assert await be.exists("tenant/a.txt") is True
    assert await be.get("tenant/a.txt") == b"hello"
    await be.delete("tenant/a.txt")
    assert await be.exists("tenant/a.txt") is False


def test_protocol_check(tmp_path):
    be = LocalStorageBackend(tmp_path)
    assert isinstance(be, StorageBackend)


def test_rejects_traversal(tmp_path):
    be = LocalStorageBackend(tmp_path / "s")
    with pytest.raises(UnsafePathError):
        be._abs("../escape.txt")
    with pytest.raises(UnsafePathError):
        be._abs("/abs/path.txt")
    with pytest.raises(UnsafePathError):
        be._abs("tenant/../../escape.txt")
    with pytest.raises(UnsafePathError):
        be._abs("")


def test_rejects_unsafe_segment(tmp_path):
    be = LocalStorageBackend(tmp_path)
    with pytest.raises(UnsafePathError):
        be._abs("tenant/bad file.txt")  # space


async def test_exists_false_on_bad_path(tmp_path):
    be = LocalStorageBackend(tmp_path)
    assert await be.exists("../nope") is False


async def test_get_missing_raises(tmp_path):
    be = LocalStorageBackend(tmp_path)
    with pytest.raises(FileNotFoundError):
        await be.get("tenant/missing.txt")


async def test_delete_missing_is_noop(tmp_path):
    be = LocalStorageBackend(tmp_path)
    await be.delete("tenant/missing.txt")


def test_root_property(tmp_path):
    be = LocalStorageBackend(tmp_path / "r")
    assert be.root.exists()
