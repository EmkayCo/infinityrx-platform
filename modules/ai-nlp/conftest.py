"""Top-level conftest — adds modules/ai-nlp to sys.path so
`src.*` imports resolve. The directory name is hyphenated so it cannot
itself be a Python package; adding it to sys.path lets `src` act as a
top-level package just for this module's tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
