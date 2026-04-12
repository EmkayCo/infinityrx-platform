"""PHI access helpers.

The ``@phi_access`` marker lives in :mod:`src.audit.decorators` and is
re-exported here so call sites can import it from a single namespace.
The middleware handles the actual logging in the same DB transaction as
the normal audit entry, which keeps both rows consistent.
"""

from __future__ import annotations

from src.audit.decorators import phi_access

__all__ = ["phi_access"]
