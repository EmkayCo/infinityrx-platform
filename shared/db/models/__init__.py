"""Aggregated import site for all shared ORM models.

Importing this package ensures every model class is registered on
``shared.db.base.Base.metadata``, which Alembic uses to autogenerate
migrations and integration tests use to create schemas.
"""

from shared.db.models import core as core  # noqa: F401
from shared.db.models.events import EventDLQEntry, ProcessedEvent  # noqa: F401

__all__ = ["core", "EventDLQEntry", "ProcessedEvent"]
