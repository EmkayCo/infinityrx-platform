"""Alembic environment for payment-processing.

Imports Base metadata and all payment_proc ORM models so that
autogenerate sees the full schema for migrations.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── sys.path setup ────────────────────────────────────────────────────────
# Add module root (for `src.*` imports) and project root (for `shared.*`)
_MODULE_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
for _p in [str(_MODULE_ROOT), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Import all ORM models so metadata is populated ────────────────────────
from src._shim.db import Base  # noqa: F401
from src.models.tables import (  # noqa: F401
    AchReturnCode,
    OfacScreeningAlert,
    OfacSdnEntry,
    PayeeEnrollment,
    Settlement,
    Submission,
    VendorAdapter,
    VendorHealthLog,
)

# Use Base metadata (all payment_proc tables)
target_metadata = Base.metadata

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
        version_table_schema="payment_proc",
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
            version_table_schema="payment_proc",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
