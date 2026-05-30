"""Session-scoped testcontainers Postgres fixture for real-DB tests.

The wave pattern through Waves 16-20 surfaced a recurring bug class:
code passed mock-backed tests but broke on the real DB (pharmacy_dir
typo in Wave 16b, core.audit_log typo in Wave 18, pgvector gap in
Wave 19, FORCE RLS finding in Wave 20 B2). Wave 21a is the
infrastructure that catches this class: spin up an ephemeral Postgres
with pgvector, apply every module's alembic chain from scratch, and
yield a connection URL to the test.

Design decisions (2026-04-20 founder direction)
-----------------------------------------------
* **Ephemeral container per session** — no shared state with dev DB.
* **testcontainers-python** — industry standard, handles teardown.
* **pgvector/pgvector:pg17 image** — Wave 19 proved stock postgres
  lacks pgvector. Already cached locally (~646MB).
* **Roles match init-multi-db.sql** — ``ifx_dev_app`` (tenant role)
  and ``ifx_dev_admin`` (BYPASSRLS) are created with the same
  passwords the dev env uses, so existing helpers like
  ``seed_as_admin()`` work unchanged.
* **Every module's alembic chain applied** — real migration ordering,
  no shortcuts. If a chain has a hidden dependency (e.g. a migration
  that assumes data exists), that's a finding we want to surface.
* **Fixture is session-scoped** — startup cost (~3-10s) amortizes
  across all integration tests in the run.

Colima note
-----------
testcontainers' ryuk reaper tries to bind-mount the Docker socket into
a watcher container. On macOS + colima, the socket path the host uses
isn't accessible from inside the VM the same way, and the mount fails.
The fixture disables ryuk via ``TESTCONTAINERS_RYUK_DISABLED=true`` —
teardown still works cleanly via the PostgresContainer context manager.
``DOCKER_HOST`` is auto-detected from the colima context if not set.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import psycopg2
import pytest

_REPO = Path(__file__).resolve().parent.parent.parent


# ── Schemas mirrored from infrastructure/scripts/init-multi-db.sql ──────────
# Source of truth is init-multi-db.sql; keep this list aligned. Any drift
# would surface as "schema 'xyz' does not exist" during migrations —
# expected failure mode for detecting drift.
_SCHEMAS: list[str] = [
    "reference", "core", "shared", "billing", "payment_proc",
    "reclaimrx", "reporting", "ai_nlp", "dataiq", "drug_db",
    "drug_database", "pharmacy_dir", "prescriber_dir", "member_mgmt",
    "edi", "edi_compliance", "medical_claims",
    "adjudication", "adjudication_engine",
    "mtm_clinical", "plan_design", "prior_auth", "program_config",
    "paysync",
    "rebate_mgmt", "rules_engine", "switch_conn", "testing_sim",
    "ebv_ebi", "tenant_config",
    "network_mgmt",
    "maxacc_registry",
]

# Modules with alembic chains — all get `alembic upgrade head` against
# the fresh container.
#
# Ordering matters in a few places:
#   - program-config runs BEFORE rules-engine (rules_engine.rule_instances
#     has a cross-schema FK to program_config.programs, added in
#     program-config's Wave 26 Phase C.1 baseline). rules-engine's FK
#     creation fails if programs doesn't exist.
#   - adjudication-engine runs AFTER program-config + rules-engine
#     because its claim_transactions eventually carries a rule_id
#     reference (though no hard FK is declared today, the ordering
#     keeps things stable if a future migration adds one).
# Within those constraints the list order is build history.
_MIGRATION_MODULES: list[str] = [
    "core-platform",        # core.* tables, most foundational
    "ai-nlp",               # ai_nlp.* with pgvector
    "program-config",       # program_config.* (owns programs for rules FK)
    "rules-engine",         # rules_engine.* (FK to program_config.programs)
    "billing",              # billing.*
    "payment-processing",   # payment_proc.*
    "drug-database",        # drug_database.*
    "pharmacy-directory",   # pharmacy_dir.*
    "prescriber-directory", # prescriber_dir.*
    "reporting",            # reporting.* (Wave 24)
    "adjudication-engine",  # adjudication_engine.* (Wave 26 Phase A-prep)
    "paysync",              # paysync.* (Wave 35 — Phase 2 PaySync foundation)
    "network-management",   # network_mgmt.* (Wave 36 — pay-to + banking + 835 dest)
    # reclaimrx excluded: two-head migration fork (0008_ml_detector_seed vs
    # 0008_sp3_extensions) — cannot use standard module-root 'alembic upgrade head'.
    # Apply explicitly via modules/reclaimrx/alembic/alembic.ini + named revision.
    # Tracked tech-debt.
    "maxacc-registry",      # maxacc_registry.* (Wave 44a — global ref data)
]


def _docker_host() -> str:
    """Resolve DOCKER_HOST from env or colima context.

    testcontainers needs an explicit socket path on colima; the default
    discovery path (/var/run/docker.sock) doesn't exist.
    """
    existing = os.environ.get("DOCKER_HOST")
    if existing:
        return existing
    colima = Path.home() / ".colima" / "default" / "docker.sock"
    if colima.exists():
        return f"unix://{colima}"
    return "unix:///var/run/docker.sock"


def _bootstrap_roles_and_schemas(superuser_url: str) -> None:
    """Replicate the test-relevant subset of init-multi-db.sql.

    * Creates ``ifx_dev_app`` and ``ifx_dev_admin`` with the same
      passwords as local dev (so ``seed_as_admin`` and tenant URL
      construction work unchanged).
    * Grants ``ifx_dev_admin`` membership in ``ifx_dev_app`` so admin
      inherits table privileges.
    * Creates the full schema list from init-multi-db.sql.
    * Installs ``pgvector``, ``uuid-ossp``, ``pgcrypto`` extensions.

    The DB owner stays as testcontainers' default ``test`` superuser;
    we grant schema/extension CREATE to ifx_dev_app so its migrations
    run with the same permissions they have in dev.
    """
    conn = psycopg2.connect(superuser_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Roles — match dev passwords so seed_as_admin works unchanged.
            cur.execute(
                "CREATE ROLE ifx_dev_app LOGIN PASSWORD 'dev_password'"
            )
            cur.execute(
                "CREATE ROLE ifx_dev_admin LOGIN PASSWORD 'dev_admin_password' BYPASSRLS"
            )
            # Admin inherits app role's table privileges.
            cur.execute("GRANT ifx_dev_app TO ifx_dev_admin")
            # Mock app role too — RLS policies list it in the TO clause
            # alongside the env-driven _APP_ROLE (default: ifx_dev_app),
            # so it must exist even though we don't connect as it in tests.
            # (PG refuses CREATE POLICY for a nonexistent role.)
            #
            # B7.3 (2026-05-11): ifx_prod_app no longer created here.
            # Migration files use os.environ.get("IFX_APP_ROLE",
            # "ifx_dev_app") so policies target dev_app (which already
            # exists) when IFX_APP_ROLE is unset. Production sets
            # IFX_APP_ROLE=ifx_prod_app explicitly; dev / test rely on
            # the dev_app default. This prevents the conftest from
            # accidentally creating ifx_prod_app on a live dev cluster.
            cur.execute("CREATE ROLE ifx_mock_app LOGIN PASSWORD 'mock_password'")

            # Grant ifx_dev_app full DB + schema privileges so its
            # migrations can CREATE/ALTER tables.
            db_name = conn.get_dsn_parameters()["dbname"]
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO ifx_dev_app")

            # Extensions (must be superuser).
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

            # Schemas owned by ifx_dev_app (matches dev).
            for schema in _SCHEMAS:
                cur.execute(
                    f'CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION ifx_dev_app'
                )
    finally:
        conn.close()


def _apply_migrations(tenant_url: str) -> None:
    """Run ``alembic upgrade head`` for each module against the fresh DB.

    Runs alembic via subprocess so each module gets a clean import
    state + explicit DATABASE_URL_SYNC. This matches how dev/CI runs
    migrations; no magic.
    """
    env = os.environ.copy()
    env["DATABASE_URL_SYNC"] = tenant_url
    # DATABASE_URL is used by some module env.py files. Keep it in sync
    # but on the async driver, since the code that reads it expects async.
    env["DATABASE_URL"] = tenant_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Ensure get_settings() is re-read if the alembic subprocess imports
    # shared.config.
    env.pop("INFINITYRX_SETTINGS_CACHE", None)

    venv_python = _REPO / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    for module in _MIGRATION_MODULES:
        module_dir = _REPO / "modules" / module
        if not (module_dir / "alembic.ini").exists():
            raise FileNotFoundError(
                f"No alembic.ini at {module_dir} — _MIGRATION_MODULES drift?"
            )
        result = subprocess.run(
            [python_bin, "-m", "alembic", "upgrade", "head"],
            cwd=str(module_dir),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"alembic upgrade head failed for {module}:\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )


@pytest.fixture(scope="session")
def integration_postgres() -> Iterator[dict]:
    """Spin up an ephemeral Postgres with pgvector, apply all module migrations.

    Yields a dict with connection URLs. Tests should prefer the tenant
    URL (``url_sync``) since it matches dev semantics — RLS applies,
    tenant context must be set. For cross-tenant seeding, use
    ``seed_as_admin()`` against the admin URL.
    """
    from testcontainers.postgres import PostgresContainer  # noqa: PLC0415

    # testcontainers env prep (see module docstring).
    os.environ.setdefault("DOCKER_HOST", _docker_host())
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

    with PostgresContainer(
        "pgvector/pgvector:pg17",
        username="ifx_test_super",
        password="super_pass",
        dbname="ifx_test",
    ) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        db_name = "ifx_test"

        # testcontainers reports the raw psycopg2-driver URL; strip the
        # driver suffix for plain psycopg2 use.
        superuser_url = (
            f"postgresql://ifx_test_super:super_pass@{host}:{port}/{db_name}"
        )
        tenant_url = (
            f"postgresql://ifx_dev_app:dev_password@{host}:{port}/{db_name}"
        )
        admin_url = (
            f"postgresql://ifx_dev_admin:dev_admin_password@{host}:{port}/{db_name}"
        )

        _bootstrap_roles_and_schemas(superuser_url)
        _apply_migrations(tenant_url)

        # Wave 21b: export DATABASE_URL_SYNC so pre-Wave-21 tests that
        # read the env directly (via psycopg2.connect or seed_as_admin)
        # see the ephemeral container without needing per-test edits.
        # Restored on fixture teardown via the context-manager.
        _prev_sync = os.environ.get("DATABASE_URL_SYNC")
        _prev_async = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL_SYNC"] = tenant_url
        os.environ["DATABASE_URL"] = tenant_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )

        try:
            yield {
                "host": host,
                "port": port,
                "db_name": db_name,
                "url_sync": tenant_url,
                "url_async": tenant_url.replace("postgresql://", "postgresql+asyncpg://", 1),
                "admin_url_sync": admin_url,
                "superuser_url_sync": superuser_url,
                "container": container,
            }
        finally:
            # Restore env on teardown.
            if _prev_sync is None:
                os.environ.pop("DATABASE_URL_SYNC", None)
            else:
                os.environ["DATABASE_URL_SYNC"] = _prev_sync
            if _prev_async is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = _prev_async
