"""Top-level conftest for reclaimrx module.

Adds modules/reclaimrx to sys.path so `src.*` imports resolve.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
