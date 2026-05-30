"""Alembic environment for reclaimrx module.

reclaimrx is intentionally EXCLUDED from infrastructure/scripts/run_migrations.sh
until the two-head migration fork (0008_ml_detector_seed vs 0008_sp3_extensions)
is merged — tracked tech-debt. Invoke explicitly:
    python -m alembic -c modules/reclaimrx/alembic/alembic.ini <cmd>
with a NAMED revision, never `head`.

target_metadata is set to None because reclaimrx ORM models are added in a
later task. This env supports upgrade-only (apply existing migration files)
until the models are wired.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── sys.path setup ────────────────────────────────────────────────────────
# env.py lives at modules/reclaimrx/alembic/env.py.
# Module root = two levels up; project root = three levels up.
_ALEMBIC_DIR = Path(__file__).resolve().parent
_MODULE_ROOT = _ALEMBIC_DIR.parent
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
for _p in [str(_MODULE_ROOT), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Metadata ──────────────────────────────────────────────────────────────
# ORM models are wired in a later task. Set to None for upgrade-only mode.
target_metadata = None

# ── Alembic config ────────────────────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow DATABASE_URL env override (for CI / Docker)
_db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (SQL script output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="reclaimrx",
        version_table="alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="reclaimrx",
            version_table="alembic_version",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
