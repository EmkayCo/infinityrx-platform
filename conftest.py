"""Root conftest — wires sys.path so both shared/ and modules/core-platform/src
are importable during test collection.

The module directory uses a dash (``core-platform``) which is not a valid
Python package name. We therefore insert the module's ``src`` directory
directly onto ``sys.path`` so its sub-packages (``infrastructure``, etc.)
import at the top level. The repo root is also added so ``shared.*`` works
without requiring an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_CORE_PLATFORM_SRC = _REPO_ROOT / "modules" / "core-platform" / "src"

for path in (_REPO_ROOT, _CORE_PLATFORM_SRC):
    sp = str(path)
    if sp not in sys.path:
        sys.path.insert(0, sp)
