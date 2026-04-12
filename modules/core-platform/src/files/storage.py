"""Pluggable storage backend for binary blobs.

Only the LocalStorageBackend ships in Phase 1 (YAGNI). The StorageBackend
Protocol defines the contract that future cloud backends (Azure Blob, S3,
GCS) must satisfy. Cloud backends are not stubbed here to keep the
"no-stub" rule clean.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    async def put(self, path: str, content: bytes) -> str: ...
    async def get(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...
    async def exists(self, path: str) -> bool: ...


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._\-]+$")


class UnsafePathError(ValueError):
    """Raised when a caller-supplied path escapes the backend root."""


def _sanitize_segments(path: str) -> list[str]:
    if not path or path.startswith("/"):
        raise UnsafePathError(f"absolute or empty path rejected: {path!r}")
    parts: list[str] = []
    for raw in path.replace("\\", "/").split("/"):
        if raw == "" or raw == ".":
            continue
        if raw == "..":
            raise UnsafePathError(f"parent traversal rejected: {path!r}")
        if not _SAFE_SEGMENT.match(raw):
            raise UnsafePathError(f"unsafe path segment rejected: {raw!r}")
        parts.append(raw)
    if not parts:
        raise UnsafePathError(f"empty path after sanitization: {path!r}")
    return parts


class LocalStorageBackend:
    """Stores blobs on the local filesystem under a fixed root.

    Sanitizes every path to prevent traversal and ensures the final
    absolute path sits inside the root directory.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _abs(self, path: str) -> Path:
        parts = _sanitize_segments(path)
        target = self._root.joinpath(*parts).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise UnsafePathError(f"resolved path escapes root: {path!r}") from exc
        return target

    async def put(self, path: str, content: bytes) -> str:
        target = self._abs(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    async def get(self, path: str) -> bytes:
        target = self._abs(path)
        if not target.exists():
            raise FileNotFoundError(path)
        return target.read_bytes()

    async def delete(self, path: str) -> None:
        target = self._abs(path)
        if target.exists():
            target.unlink()

    async def exists(self, path: str) -> bool:
        try:
            target = self._abs(path)
        except UnsafePathError:
            return False
        return target.exists()
