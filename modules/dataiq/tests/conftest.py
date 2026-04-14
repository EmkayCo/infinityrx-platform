"""Shared test fixtures for DataIQ module tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the module src is importable as `src.*`
_src_path = str(Path(__file__).parent.parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))
