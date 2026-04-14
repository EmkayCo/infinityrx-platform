"""Alembic environment for the pharmacy-directory module.

Manages the ``pharmacy_dir`` schema. Uses version_table_schema="pharmacy_dir"
so Alembic's bookkeeping table stays inside the same schema it manages,
preventing collisions with other modules' alembic_version tables.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Ensure the repo root is on sys.path so ``shared.*`` and ``src.*`` imports work.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]
_MODULE_ROOT = _HERE.parents[2]

for _p in (str(_REPO_ROOT), str(_MODULE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config import get_settings  # noqa: E402
from src.models.base import PharmacyBase as Base  # noqa: E402
import src.models.tables  # noqa: E402, F401  — registers existing models
import src.models.ncpdp_tables  # noqa: E402, F401  — registers NCPDP models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_SETTINGS = get_settings()
_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
config.set_main_option("sqlalchemy.url", _DB_URL)

_SCHEMA = "pharmacy_dir"


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Restrict autogenerate to the ``pharmacy_dir`` schema."""
    if type_ == "table":
        return getattr(obj, "schema", None) == _SCHEMA
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema=_SCHEMA,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=_SCHEMA,
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
