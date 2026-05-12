"""B9.A C4 (post-gate-close F1) — Render-time tests for fdb_mtl_revoke.sql.tmpl.

Codex B9.A GATE-CLOSE R1 HIGH 1 fix: the template uses FOUR
placeholders ({{SCHEMA}}, {{MTL_TABLES}}, {{APP_ROLES}},
{{APP_ROLES_QUOTED}}). The B9.G migration helper must substitute
all four — leaving any one un-substituted ships a broken migration.

These tests render the template with realistic inputs and assert:
  1. No `{{...}}` token survives the substitution.
  2. The REVOKE statement names every table in the input list (the
     codex bug — only the first table was being qualified — would
     manifest as exactly ONE table appearing in the output).
  3. The verification-block grantee list uses QUOTED role literals
     (information_schema.role_table_grants.grantee is text).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[4]
    / "infrastructure" / "scripts" / "lib" / "fdb_mtl_revoke.sql.tmpl"
)


def _render(
    *,
    schema: str,
    tables: tuple[str, ...],
    roles: tuple[str, ...],
) -> str:
    """Mirror the substitution recipe documented in the template header."""
    body = _TEMPLATE_PATH.read_text(encoding="utf-8")
    tables_qualified = ", ".join(f"{schema}.{t}" for t in tables)
    roles_unquoted = ", ".join(roles)
    roles_quoted = ", ".join(f"'{r}'" for r in roles)
    return (
        body
        .replace("{{SCHEMA}}", schema)
        .replace("{{MTL_TABLES}}", tables_qualified)
        .replace("{{APP_ROLES}}", roles_unquoted)
        .replace("{{APP_ROLES_QUOTED}}", roles_quoted)
    )


# ---------------------------------------------------------------------------
# Render contract
# ---------------------------------------------------------------------------


def test_template_file_exists() -> None:
    assert _TEMPLATE_PATH.exists(), f"template missing at {_TEMPLATE_PATH}"


def test_full_render_leaves_no_placeholders() -> None:
    """Any {{...}} token after substitution would ship a broken migration."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_test_lex_master", "mtl_test_lex_xref"),
        roles=("ifx_dev_app", "ifx_mock_app", "ifx_prod_app"),
    )
    leftover = re.findall(r"\{\{[A-Za-z_]+\}\}", rendered)
    assert not leftover, (
        f"Template has un-substituted placeholders: {leftover}. "
        f"All four ({{SCHEMA}}, {{MTL_TABLES}}, {{APP_ROLES}}, "
        f"{{APP_ROLES_QUOTED}}) must be replaced."
    )


def test_revoke_statement_names_every_table() -> None:
    """Codex HIGH 1: previous template was `ON {{SCHEMA}}.{{MTL_TABLES}}` — only the first table was qualified."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_alpha", "mtl_beta", "mtl_gamma"),
        roles=("ifx_dev_app",),
    )
    # Every table appears schema-qualified in the REVOKE clause.
    for table in ("mtl_alpha", "mtl_beta", "mtl_gamma"):
        assert f"drug_database.{table}" in rendered, (
            f"Table {table!r} missing from rendered REVOKE — schema "
            f"prefix was not broadcast across the comma list."
        )
    # Sanity: the REVOKE keyword appears once (single statement, not three).
    assert rendered.count("REVOKE INSERT, UPDATE, DELETE") == 1


def test_verification_block_uses_quoted_role_literals() -> None:
    """information_schema.role_table_grants.grantee is text — needs 'role' not role."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_x",),
        roles=("ifx_dev_app", "ifx_mock_app"),
    )
    # Quoted form appears in the IN (...) clause of the verification block.
    assert "'ifx_dev_app'" in rendered
    assert "'ifx_mock_app'" in rendered
    # Plus, the REVOKE clause uses the UNQUOTED form (identifiers, not literals).
    revoke_block = rendered.split("-- 2)")[0]
    assert "FROM ifx_dev_app, ifx_mock_app" in revoke_block


def test_render_with_single_table_and_single_role() -> None:
    """Minimum-size render — degenerate cases must still substitute cleanly."""
    rendered = _render(
        schema="drug_database",
        tables=("mtl_only",),
        roles=("ifx_dev_app",),
    )
    assert "drug_database.mtl_only" in rendered
    assert "FROM ifx_dev_app" in rendered
    assert "'ifx_dev_app'" in rendered
    leftover = re.findall(r"\{\{[A-Za-z_]+\}\}", rendered)
    assert not leftover


def test_template_still_carries_critical_statements() -> None:
    """Sanity — F1 cleanup didn't accidentally drop the REVOKE / verification."""
    body = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "REVOKE INSERT, UPDATE, DELETE" in body
    assert "RAISE EXCEPTION" in body  # verification block
    assert "information_schema.role_table_grants" in body
    # All four placeholders documented somewhere in the template header.
    for placeholder in (
        "{{SCHEMA}}", "{{MTL_TABLES}}", "{{APP_ROLES}}", "{{APP_ROLES_QUOTED}}"
    ):
        assert placeholder in body, f"{placeholder} disappeared from template"
