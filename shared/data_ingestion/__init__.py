"""Shared data ingestion framework.

Provides base classes, download utilities, run tracking, scheduling, and
API routes for all IFX reference-data ingestion pipelines (FDA NDC, CMS
NADAC, NPPES, etc.).

Import paths for teammates 2-6:
    from shared.data_ingestion.base import DataSourceIngester, IngestionResult
    from shared.data_ingestion.scheduler import IngestionScheduler, DEFAULT_SCHEDULES
    from shared.data_ingestion.field_registry import FieldRegistry, FieldMetadata, register_field
    from shared.data_ingestion.models import IngestionRun, IngestionSchedule
    from shared.data_ingestion.api.routes import router as ingestion_router
"""

from shared.data_ingestion.base import DataSourceIngester, IngestionResult
from shared.data_ingestion.field_registry import FieldMetadata, FieldRegistry, register_field
from shared.data_ingestion.scheduler import DEFAULT_SCHEDULES, IngestionScheduler

__all__ = [
    "DEFAULT_SCHEDULES",
    "DataSourceIngester",
    "FieldMetadata",
    "FieldRegistry",
    "IngestionResult",
    "IngestionScheduler",
    "register_field",
]
