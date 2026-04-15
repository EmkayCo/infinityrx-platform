"""Smoke tests for the demo environment seed script.

Runs dump_fixtures() into a tmp dir and asserts:
  * Every manufacturer + program + drug appears.
  * Claim count matches the requested target (± BRR/duplicate fanout).
  * FWA-tagged claims exist for all four seeded patterns.
  * Output is deterministic given the same seed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Make scripts/ importable from the repo root
import sys
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.setup_demo import dump_fixtures  # noqa: E402


def test_dump_fixtures_produces_expected_counts(tmp_path: Path) -> None:
    summary = dump_fixtures(tmp_path, claim_count=500)
    assert summary["tenant"] == "infinityrx-demo"
    assert summary["manufacturers"] == 6
    # 11 programs across 6 fictional manufacturers
    assert 10 <= summary["programs"] <= 12
    assert summary["drugs"] == 10
    # claim count grows by BRR pattern (2 claims per pattern) + duplicate (2 per dup)
    assert summary["claims"] >= 500
    assert summary["fwa_patterns_seeded"] >= 50


def test_every_fwa_pattern_represented(tmp_path: Path) -> None:
    dump_fixtures(tmp_path, claim_count=500)
    claims = json.loads((tmp_path / "claims.json").read_text())
    tags = {c.get("_fwa_tag") for c in claims}
    assert "bill_reverse_rebill" in tags
    assert "quantity_outlier" in tags
    assert "duplicate_submission" in tags
    assert "excluded_entity" in tags


def test_deterministic_output(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    summary_a = dump_fixtures(dir_a, claim_count=200)
    summary_b = dump_fixtures(dir_b, claim_count=200)
    # Compare everything except the path (different tmp dirs per run)
    a = {k: v for k, v in summary_a.items() if k != "output_dir"}
    b = {k: v for k, v in summary_b.items() if k != "output_dir"}
    assert a == b
    claims_a = (dir_a / "claims.json").read_text()
    claims_b = (dir_b / "claims.json").read_text()
    assert claims_a == claims_b, "demo claim generation must be deterministic"


def test_all_demo_drug_names_appear(tmp_path: Path) -> None:
    from scripts.demo_fixtures import DEMO_DRUGS

    dump_fixtures(tmp_path, claim_count=2000)
    claims = json.loads((tmp_path / "claims.json").read_text())
    names_in_claims = {c["drug_name"] for c in claims}
    for drug in DEMO_DRUGS:
        assert drug.demo_name in names_in_claims, f"drug {drug.demo_name} never appeared"
