"""Root conftest — adds src and platform root (for shared/) to sys.path."""
from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent
_PLATFORM_ROOT = _MODULE_ROOT.parents[1]

sys.path.insert(0, str(_MODULE_ROOT))
sys.path.insert(0, str(_PLATFORM_ROOT))
