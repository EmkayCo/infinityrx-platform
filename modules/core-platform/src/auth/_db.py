"""Stand-in database session dependency.

INTEGRATION NOTE
================
This file exists solely to provide the ``get_session`` FastAPI dependency
key that ``src.auth`` routers depend on while Teammate 1's
``shared.db.session`` is still in progress. At integration time every
import of ``src.auth._db.get_session`` will be rewritten to
``shared.db.session.get_session`` and this module will be deleted.

``get_session`` here is intentionally an unimplemented placeholder: tests
and application composition inject a concrete session factory via
``app.dependency_overrides[get_session]``. If the dependency were ever
called without an override it would raise, making the misconfiguration
loud rather than silently returning None.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session


def get_session() -> Iterator[Session]:  # pragma: no cover - overridden in tests and at wire-up
    raise RuntimeError(
        "src.auth._db.get_session must be overridden via FastAPI "
        "dependency_overrides or replaced by shared.db.session.get_session"
    )
    yield  # pragma: no cover  # keeps function a generator for FastAPI introspection
