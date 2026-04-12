"""Alembic environment for the core-platform module.

Uses SQLAlchemy's async engine because the project does not install a sync
Postgres driver. ``version_table_schema="core"`` keeps Alembic's bookkeeping
table inside the same schema it manages, so module migrations never collide
with other modules' alembic_version tables.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Ensure the repo root is on sys.path so ``shared.*`` imports succeed.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.config import get_settings  # noqa: E402
from shared.db.base import Base  # noqa: E402
from shared.db.models import core as _core_models  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_SETTINGS = get_settings()
# Prefer the explicit sync URL if provided; otherwise fall back to async URL.
_DB_URL = _SETTINGS.DATABASE_URL_SYNC or _SETTINGS.DATABASE_URL
config.set_main_option("sqlalchemy.url", _DB_URL)


def _include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Restrict autogenerate to the ``core`` schema."""
    if type_ == "table":
        return obj.schema == "core"
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="core",
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="core",
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
