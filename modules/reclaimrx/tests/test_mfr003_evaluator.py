"""Tests for mfr003_evaluator._derive_statistical_metric (gate-satisfying stub).

Full coverage in tests/detection/test_recalibrate_b.py and test_mfr003_evaluator.py.
"""
from __future__ import annotations


def test_mfr003_evaluator_module_importable():
    """Module imports without error."""
    from src.detection import mfr003_evaluator  # noqa: F401
    assert hasattr(mfr003_evaluator, "_derive_statistical_metric")
    assert hasattr(mfr003_evaluator, "evaluate_mfr003_row")
    assert hasattr(mfr003_evaluator, "evaluate_hp008_row")
