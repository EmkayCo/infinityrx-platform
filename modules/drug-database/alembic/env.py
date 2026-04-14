"""Alembic environment for the drug-database module.

Manages the ``drug_database`` schema only — never touches other module schemas.
Uses ``version_table_schema="drug_database"`` so Alembic's version table lives
inside the drug_database schema and does not collide with other modules.

Revision chain:
  0001_ndc    → drugs, drug_packages, drug_active_ingredients, drug_pharm_classes
  0002        → reserved for pricing data (Teammate 4)
  0003        → reserved for Orange Book cross-ref (Teammate 5)
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Ensure the repo root is on sys.path so ``shared.*`` and ``modules.*`` imports succeed.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.config import get_settings  # noqa: E402

# Add the drug-database module root to sys.path so src.* imports resolve.
_MODULE_ROOT = _REPO_ROOT / "modules" / "drug-database"
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

# Import drug_database NDC models to populate NDCBase.metadata
from src.models.ndc_tables import NDCBase  # noqa: E402, F401
import src.models.ndc_tables  # noqa: E402, F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = NDCBase.metadata

_SETTINGS = get_settings()
_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
config.set_main_option("sqlalchemy.url", _DB_URL)

_MANAGED_SCHEMA = "drug_database"


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Restrict autogenerate to the drug_database schema."""
    if type_ == "table":
        return getattr(obj, "schema", None) == _MANAGED_SCHEMA
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema=_MANAGED_SCHEMA,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=_MANAGED_SCHEMA,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": _DB_URL},
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
