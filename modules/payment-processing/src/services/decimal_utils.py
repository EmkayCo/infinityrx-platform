"""Payment-processing money helpers — re-export of ``shared.utils.money``.

Canonical implementation lives in :mod:`shared.utils.money`. This file
remains only as a compatibility shim so existing imports of
``src.services.decimal_utils`` continue to resolve.
"""

from __future__ import annotations

from shared.utils.money import money, penny_allocate

__all__ = ["money", "penny_allocate"]
