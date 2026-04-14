"""Root conftest for prescriber-directory module.

Adds the module root to sys.path so `src.*` imports work in all test files.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
