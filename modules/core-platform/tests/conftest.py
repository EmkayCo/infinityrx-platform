"""Pytest configuration for the core-platform module.

Adds ``modules/core-platform`` to ``sys.path`` so that code inside the
module can be imported as ``src.*`` (mirroring the directory layout the
module ships with once it gets its own pyproject at integration time).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

# Ensure tests have a predictable JWT secret before any shared.auth import.
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault("JWT_EXPIRES_MINUTES", "60")
os.environ.setdefault("JWT_REFRESH_EXPIRES_MINUTES", "10080")
