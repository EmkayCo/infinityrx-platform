"""Tests for credentialing risk-based routing — 100% coverage required."""
from __future__ import annotations


from src.services.credentialing import determine_risk_queue


class TestDetermineRiskQueue:
    def test_low_risk_all_pass_returns_fast_track(self) -> None:
        assert determine_risk_queue(10, all_automated_pass=True) == "fast_track"

    def test_low_risk_boundary_25_all_pass_fast_track(self) -> None:
        assert determine_risk_queue(25, all_automated_pass=True) == "fast_track"

    def test_low_risk_but_checks_failed_returns_standard(self) -> None:
        assert determine_risk_queue(10, all_automated_pass=False) == "standard"

    def test_medium_risk_26_returns_standard(self) -> None:
        assert determine_risk_queue(26, all_automated_pass=True) == "standard"

    def test_medium_risk_50_returns_standard(self) -> None:
        assert determine_risk_queue(50, all_automated_pass=True) == "standard"

    def test_high_risk_51_returns_enhanced(self) -> None:
        assert determine_risk_queue(51, all_automated_pass=True) == "enhanced"

    def test_high_risk_100_returns_enhanced(self) -> None:
        assert determine_risk_queue(100, all_automated_pass=False) == "enhanced"

    def test_none_risk_returns_standard(self) -> None:
        assert determine_risk_queue(None, all_automated_pass=True) == "standard"

    def test_recent_ownership_change_always_enhanced(self) -> None:
        assert determine_risk_queue(5, all_automated_pass=True, recent_ownership_change=True) == "enhanced"

    def test_prior_fraud_flags_always_enhanced(self) -> None:
        assert determine_risk_queue(5, all_automated_pass=True, prior_fraud_flags=True) == "enhanced"

    def test_low_risk_ownership_change_overrides_to_enhanced(self) -> None:
        # Ownership change beats good risk score
        assert determine_risk_queue(0, all_automated_pass=True, recent_ownership_change=True) == "enhanced"

    def test_fraud_flags_beats_low_score(self) -> None:
        assert determine_risk_queue(0, all_automated_pass=True, prior_fraud_flags=True) == "enhanced"
