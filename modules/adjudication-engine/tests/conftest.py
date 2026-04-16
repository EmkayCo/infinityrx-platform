"""Shared fixtures for adjudication-engine module tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Add module root so `from src.services...` works, and repo root so `shared.*` works.
_MODULE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _MODULE_ROOT.parent.parent

for p in (_MODULE_ROOT, _REPO_ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
