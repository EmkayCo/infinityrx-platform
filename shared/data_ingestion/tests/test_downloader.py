"""Tests for shared.data_ingestion.downloader.

Verifies:
- Retry on 5xx (with respx mocking)
- Streaming write to .part then rename on success
- SHA-256 matches reference bytes
- ZIP extraction returns the directory
- Size guard raises DownloadSizeExceededError
"""

from __future__ import annotations

import asyncio
import hashlib
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from shared.data_ingestion.downloader import (
    DownloadError,
    DownloadSizeExceededError,
    compute_sha256,
    download_to_file,
    unzip_if_zipped,
)

# ---------------------------------------------------------------------------
# compute_sha256
# ---------------------------------------------------------------------------


def test_compute_sha256_matches_hashlib(tmp_path: Path) -> None:
    """SHA-256 computed by compute_sha256 must match hashlib reference."""
    content = b"reference content for hashing 12345"
    f = tmp_path / "test.txt"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(f) == expected


def test_compute_sha256_streams_without_loading(tmp_path: Path) -> None:
    """compute_sha256 must produce the correct digest for a multi-chunk file."""
    # Write exactly 3 x 65536 bytes so we cross the chunk boundary
    content = b"X" * (3 * 65536)
    f = tmp_path / "big.bin"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(f) == expected


# ---------------------------------------------------------------------------
# unzip_if_zipped
# ---------------------------------------------------------------------------


def test_unzip_if_zipped_returns_directory_for_zip(tmp_path: Path) -> None:
    """ZIP files must be extracted; returned path must be a directory."""
    # Create a ZIP with one member
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("hello.txt", "hello world")

    result = unzip_if_zipped(zip_path, tmp_path)
    assert result.is_dir()
    assert (result / "hello.txt").read_text() == "hello world"


def test_unzip_if_zipped_returns_original_for_non_zip(tmp_path: Path) -> None:
    """Non-ZIP files must be returned unchanged."""
    f = tmp_path / "data.txt"
    f.write_bytes(b"plain text data")

    result = unzip_if_zipped(f, tmp_path)
    assert result == f


def test_unzip_extracts_nested_members(tmp_path: Path) -> None:
    """All members of a ZIP, including nested paths, must be extracted."""
    zip_path = tmp_path / "nested.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subdir/file.csv", "a,b,c")
        zf.writestr("root.txt", "root")

    result = unzip_if_zipped(zip_path, tmp_path)
    assert (result / "subdir" / "file.csv").exists()
    assert (result / "root.txt").exists()


# ---------------------------------------------------------------------------
# download_to_file — success path
# ---------------------------------------------------------------------------


@respx.mock
def test_download_writes_part_then_renames(tmp_path: Path) -> None:
    """Downloaded bytes must be written to .part first, then renamed on success."""
    content = b"ndc reference data payload"

    respx.get("http://test.example.com/ndc.txt").mock(
        return_value=httpx.Response(200, content=content)
    )

    result = asyncio.run(
        download_to_file("http://test.example.com/ndc.txt", tmp_path)
    )

    assert result.exists()
    assert result.name == "ndc.txt"
    assert result.read_bytes() == content
    # .part file must not exist after success
    assert not (tmp_path / "ndc.txt.part").exists()


@respx.mock
def test_download_progress_callback_called(tmp_path: Path) -> None:
    """The progress callback must be invoked with cumulative byte count."""
    content = b"A" * 1000
    calls: list[tuple[int, int | None]] = []

    respx.get("http://test.example.com/prog.txt").mock(
        return_value=httpx.Response(200, content=content)
    )

    asyncio.run(
        download_to_file(
            "http://test.example.com/prog.txt",
            tmp_path,
            progress_callback=lambda downloaded, total: calls.append((downloaded, total)),
        )
    )

    assert len(calls) > 0
    # Final call must report all bytes downloaded
    final_downloaded = calls[-1][0]
    assert final_downloaded == len(content)


@respx.mock
def test_download_custom_filename(tmp_path: Path) -> None:
    """When filename= is specified, the file must use that name."""
    respx.get("http://test.example.com/data.bin").mock(
        return_value=httpx.Response(200, content=b"data")
    )

    result = asyncio.run(
        download_to_file(
            "http://test.example.com/data.bin",
            tmp_path,
            filename="custom_name.bin",
        )
    )

    assert result.name == "custom_name.bin"


# ---------------------------------------------------------------------------
# download_to_file — retry on 5xx
# ---------------------------------------------------------------------------


@respx.mock
def test_download_retries_on_503_then_succeeds(tmp_path: Path) -> None:
    """A 503 response must trigger a retry; success on second attempt."""
    content = b"recovered data"
    route = respx.get("http://test.example.com/retry.txt")
    route.side_effect = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(200, content=content),
    ]

    result = asyncio.run(
        download_to_file("http://test.example.com/retry.txt", tmp_path)
    )
    assert result.read_bytes() == content


@respx.mock
def test_download_raises_after_all_retries_exhausted(tmp_path: Path) -> None:
    """When all retry attempts return 5xx, DownloadError must be raised.

    The downloader makes 1 initial attempt + len(_RETRY_DELAYS) retries.
    We must provide one mock response per attempt.
    """
    from shared.data_ingestion.downloader import _RETRY_DELAYS

    total_attempts = len(_RETRY_DELAYS) + 1
    route = respx.get("http://test.example.com/fail.txt")
    route.side_effect = [
        httpx.Response(503, text="down")
        for _ in range(total_attempts)
    ]

    with pytest.raises(DownloadError):
        asyncio.run(
            download_to_file("http://test.example.com/fail.txt", tmp_path)
        )


@respx.mock
def test_download_does_not_retry_on_404(tmp_path: Path) -> None:
    """A 404 response must NOT be retried — raises DownloadError immediately."""
    respx.get("http://test.example.com/gone.txt").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    with pytest.raises(DownloadError):
        asyncio.run(
            download_to_file("http://test.example.com/gone.txt", tmp_path)
        )


# ---------------------------------------------------------------------------
# download_to_file — size guard
# ---------------------------------------------------------------------------


@respx.mock
def test_download_raises_when_content_length_exceeds_limit(tmp_path: Path) -> None:
    """Content-Length header exceeding max_bytes must raise DownloadSizeExceededError."""
    respx.get("http://test.example.com/huge.bin").mock(
        return_value=httpx.Response(
            200,
            content=b"X" * 100,
            headers={"Content-Length": "9999999999"},  # > default max
        )
    )

    with pytest.raises(DownloadSizeExceededError):
        asyncio.run(
            download_to_file(
                "http://test.example.com/huge.bin",
                tmp_path,
                max_bytes=1024,  # 1 KiB
            )
        )


@respx.mock
def test_download_raises_when_streamed_bytes_exceed_limit(tmp_path: Path) -> None:
    """Bytes accumulated during streaming exceeding max_bytes must raise."""
    # No Content-Length header — guard fires during streaming
    respx.get("http://test.example.com/sneaky.bin").mock(
        return_value=httpx.Response(200, content=b"Y" * 2000)
    )

    with pytest.raises(DownloadSizeExceededError):
        asyncio.run(
            download_to_file(
                "http://test.example.com/sneaky.bin",
                tmp_path,
                max_bytes=500,
            )
        )


# ---------------------------------------------------------------------------
# download_to_file — transport error retry
# ---------------------------------------------------------------------------


@respx.mock
def test_download_retries_on_transport_error(tmp_path: Path) -> None:
    """A TransportError must trigger a retry."""
    content = b"data after transport error"
    route = respx.get("http://test.example.com/transport.txt")
    route.side_effect = [
        httpx.TransportError("connection reset"),
        httpx.Response(200, content=content),
    ]

    result = asyncio.run(
        download_to_file("http://test.example.com/transport.txt", tmp_path)
    )
    assert result.read_bytes() == content
