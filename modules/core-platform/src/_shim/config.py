"""Shim settings. Real version lives in shared/ (T1)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "./storage")
    SAM_API_KEY: str = os.getenv("SAM_API_KEY", "")
    OIG_EXCLUSION_URL: str = os.getenv(
        "OIG_EXCLUSION_URL",
        "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv",
    )
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    ALLOWED_CONTENT_TYPES: str = os.getenv(
        "ALLOWED_CONTENT_TYPES",
        "application/pdf,text/csv,image/png,image/jpeg,application/octet-stream,text/plain",
    )


settings = Settings()
