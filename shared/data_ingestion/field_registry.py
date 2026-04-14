"""Field registry: in-memory catalog of source → table → column metadata.

Teammates 2-6 call :func:`register_field` at module import time to declare
which source file columns map to which database fields. The
``/api/v1/data-ingestion/field-catalog`` endpoint dumps the full registry.

Example registration::

    from shared.data_ingestion.field_registry import register_field

    register_field(
        source="fda_ndc",
        table="drug_database.ndc_products",
        column="ndc_11",
        description="11-digit NDC in 5-4-2 format",
        source_file="product.txt",
        source_position="PRODUCTNDC",
        data_type="str",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldMetadata:
    """Metadata for a single source-to-database field mapping."""

    source: str
    table: str
    column: str
    description: str
    source_file: str
    source_position: str  # column name or zero-based index
    data_type: str  # str | int | Decimal | date | bool


class FieldRegistry:
    """In-memory catalog of all registered field mappings.

    A singleton instance :data:`registry` is used by default. Callers may
    create their own instance for isolated testing.
    """

    def __init__(self) -> None:
        self._fields: list[FieldMetadata] = []

    def register(
        self,
        *,
        source: str,
        table: str,
        column: str,
        description: str,
        source_file: str,
        source_position: str,
        data_type: str,
    ) -> FieldMetadata:
        """Add a field mapping to the registry and return the :class:`FieldMetadata`."""
        meta = FieldMetadata(
            source=source,
            table=table,
            column=column,
            description=description,
            source_file=source_file,
            source_position=source_position,
            data_type=data_type,
        )
        self._fields.append(meta)
        return meta

    def all_fields(self) -> list[FieldMetadata]:
        """Return all registered fields (defensive copy)."""
        return list(self._fields)

    def fields_for_source(self, source: str) -> list[FieldMetadata]:
        """Return all fields belonging to *source*."""
        return [f for f in self._fields if f.source == source]

    def as_dict_list(self) -> list[dict[str, Any]]:
        """Serialize the full registry as a list of plain dicts."""
        return [
            {
                "source": f.source,
                "table": f.table,
                "column": f.column,
                "description": f.description,
                "source_file": f.source_file,
                "source_position": f.source_position,
                "data_type": f.data_type,
            }
            for f in self._fields
        ]


# Module-level singleton — teammates import and call register_field()
registry = FieldRegistry()


def register_field(
    *,
    source: str,
    table: str,
    column: str,
    description: str,
    source_file: str,
    source_position: str,
    data_type: str,
) -> FieldMetadata:
    """Convenience wrapper around the module-level :data:`registry`.

    Call at module import time from each data-source implementation::

        register_field(source="fda_ndc", table="drug_database.ndc_products",
                       column="ndc_11", ...)
    """
    return registry.register(
        source=source,
        table=table,
        column=column,
        description=description,
        source_file=source_file,
        source_position=source_position,
        data_type=data_type,
    )


__all__ = ["FieldMetadata", "FieldRegistry", "register_field", "registry"]
