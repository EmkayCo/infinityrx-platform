"""Top-level conftest — adds modules/payment-processing to sys.path so
`src.*` imports resolve without the hyphenated directory being a package.
Also pins the repo root so ``shared.*`` imports resolve for the tenant
isolation primitives that the session factory depends on.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
