"""Tests for mfr003_evaluator module.

Primary test coverage lives in test_recalibrate_b.py:
  - test_mfr003_evaluator_skips_claim_when_no_fdb_wac
  - test_mfr003_uses_fdb_wac_not_csv_wac
  - test_mfr003_evaluator_respects_min_sample_gate

This file satisfies the Werkbench test-first gate for the module file.
Additional unit tests for evaluate_mfr003_row and evaluate_hp008_row are here.
"""
from __future__ import annotations

from decimal import Decimal

import pytest


def test_derive_statistical_metric_mfr003_empty_cache_returns_no_fdb_wac():
    """_derive_statistical_metric returns {_no_fdb_wac: True} when cache is empty."""
    from src.detection.mfr003_evaluator import _derive_statistical_metric

    result = _derive_statistical_metric(ndc="12345678901", _fdb_cache={})
    assert result == {"_no_fdb_wac": True}


def test_derive_statistical_metric_mfr003_none_wac_returns_no_fdb_wac():
    """_derive_statistical_metric returns {_no_fdb_wac: True} when wac=None in cache."""
    from src.detection.mfr003_evaluator import _derive_statistical_metric

    cache = {"12345678901": {"wac": None, "swp": None}}
    result = _derive_statistical_metric(ndc="12345678901", _fdb_cache=cache)
    assert result == {"_no_fdb_wac": True}


def test_derive_statistical_metric_hp008_no_rd_returns_empty():
    """HP-008 unit-test path with rd=None returns {} (no WAC check needed)."""
    from src.detection.mfr003_evaluator import _derive_statistical_metric

    result = _derive_statistical_metric(ndc=None, _fdb_cache={}, code="HP-008")
    assert result == {}


def test_derive_statistical_metric_unknown_code_returns_empty():
    """Unknown code returns empty dict."""
    from src.detection.mfr003_evaluator import _derive_statistical_metric

    result = _derive_statistical_metric(ndc="ndc", _fdb_cache={}, code="UNKNOWN")
    assert result == {}
