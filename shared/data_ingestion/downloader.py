"""File downloader for reference-data ingestion pipelines.

Provides streaming HTTP download with retry/backoff, SHA-256 checksum
computation, ZIP extraction, and a configurable max-size guard. All
operations avoid loading the full file into memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import zipfile
from collections.abc import Callable
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Default maximum download size: 2 GiB
_DEFAULT_MAX_BYTES: int = 2 * 1024 * 1024 * 1024

# Retry delays in seconds (exponential: 1s, 2s, 4s)
_RETRY_DELAYS: tuple[float, float, float] = (1.0, 2.0, 4.0)


class DownloadSizeExceededError(Exception):
    """Raised when a download exceeds the configured size limit."""


class DownloadError(Exception):
    """Raised when all retry attempts are exhausted."""


async def download_to_file(
    url: str,
    dest_dir: Path,
    *,
    filename: str | None = None,
    progress_callback: Callable[[int, int | None], None] | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout_seconds: float = 300.0,
) -> Path:
    """Stream-download *url* into *dest_dir*, retrying on transient errors.

    Parameters
    ----------
    url:
        Full HTTP/HTTPS URL to fetch.
    dest_dir:
        Directory in which to write the file. Must exist.
    filename:
        Override the filename. When None, derived from the URL's last path
        component.
    progress_callback:
        Optional ``(bytes_downloaded, total_bytes_or_None) -> None`` called
        after each chunk. ``total_bytes_or_None`` is ``None`` when the server
        does not send ``Content-Length``.
    max_bytes:
        Hard limit on download size. Raises :class:`DownloadSizeExceededError`
        if exceeded.
    timeout_seconds:
        Per-request read timeout in seconds.

    Returns
    -------
    Path
        The path to the successfully written file.

    Raises
    ------
    DownloadSizeExceededError
        If the file exceeds *max_bytes*.
    DownloadError
        If all retry attempts are exhausted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    resolved_filename = filename or _filename_from_url(url)
    final_path = dest_dir / resolved_filename
    part_path = dest_dir / f"{resolved_filename}.part"

    last_error: Exception | None = None
    attempts = len(_RETRY_DELAYS) + 1  # 1 initial + len(delays) retries

    for attempt in range(attempts):
        if attempt > 0:
            delay = _RETRY_DELAYS[attempt - 1]
            logger.warning(
                "Retrying download after error",
                extra={
                    "ingest_url": url,
                    "ingest_attempt": attempt,
                    "ingest_retry_delay_s": delay,
                },
            )
            await asyncio.sleep(delay)

        try:
            downloaded = await _stream_to_file(
                url=url,
                part_path=part_path,
                max_bytes=max_bytes,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
            )
        except DownloadSizeExceededError:
            raise  # Never retry size violations
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and (
                exc.response.status_code < 500
            ):
                # 4xx errors are not transient — do not retry
                raise DownloadError(
                    f"Non-retryable HTTP error {exc.response.status_code} for {url}"
                ) from exc
            logger.warning(
                "Transient download error",
                extra={"ingest_url": url, "ingest_error": str(exc)},
            )
            continue

        # Success: atomically rename .part -> final. Use os.replace (not
        # Path.rename) because Path.rename inherits POSIX semantics — it fails
        # on Windows when the target already exists (WinError 183). os.replace
        # is atomic AND overwrites cross-platform.
        import os as _os
        _os.replace(part_path, final_path)
        logger.info(
            "Download complete",
            extra={
                "ingest_url": url,
                "ingest_dest": str(final_path),
                "ingest_bytes": downloaded,
            },
        )
        return final_path

    # All attempts exhausted
    raise DownloadError(
        f"Download failed after {attempts} attempts for {url}"
    ) from last_error


async def _stream_to_file(
    url: str,
    part_path: Path,
    max_bytes: int,
    timeout_seconds: float,
    progress_callback: Callable[[int, int | None], None] | None,
) -> int:
    """Core streaming logic. Returns total bytes written."""
    timeout = httpx.Timeout(timeout_seconds, connect=30.0)
    async with (
        httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client,
        client.stream("GET", url) as response,
    ):
            response.raise_for_status()

            content_length_raw = response.headers.get("content-length")
            total: int | None = (
                int(content_length_raw)
                if content_length_raw and content_length_raw.isdigit()
                else None
            )
            if total is not None and total > max_bytes:
                raise DownloadSizeExceededError(
                    f"Content-Length {total} exceeds max_bytes={max_bytes}"
                )

            downloaded = 0
            with part_path.open("wb") as fh:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise DownloadSizeExceededError(
                            f"Downloaded {downloaded} bytes exceeds max_bytes={max_bytes}"
                        )
                    fh.write(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded, total)

    return downloaded


def _filename_from_url(url: str) -> str:
    """Extract a safe filename from a URL path component."""
    path_part = url.split("?")[0].rstrip("/")
    name = path_part.split("/")[-1]
    return name or "download"


def compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of *path* by streaming it.

    Never loads the file into memory. Suitable for multi-GB files.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def unzip_if_zipped(path: Path, dest_dir: Path) -> Path:
    """If *path* is a ZIP archive, extract it to *dest_dir* and return the directory.

    If *path* is not a ZIP file, return *path* unchanged.

    Parameters
    ----------
    path:
        File to inspect.
    dest_dir:
        Destination directory for extraction. Created if it does not exist.

    Returns
    -------
    Path
        The extracted directory path if *path* was a ZIP, else *path* itself.
    """
    if not zipfile.is_zipfile(path):
        return path

    extract_dir = dest_dir / path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "r") as zf:
        zf.extractall(extract_dir)

    logger.info(
        "ZIP extracted",
        extra={"ingest_source_zip": str(path), "ingest_extract_dir": str(extract_dir)},
    )
    return extract_dir


__all__ = [
    "DownloadError",
    "DownloadSizeExceededError",
    "compute_sha256",
    "download_to_file",
    "unzip_if_zipped",
]
