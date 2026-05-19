"""Integration test: GraphAnalysisJob._run_graph_computation without mocks."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.jobs.graph_analysis_job import GraphAnalysisJob
from src.models.tables import FlaggedClaim

@pytest.fixture
def dense_pharmacy_prescriber_ring(db, tenant_a_id):
    pharm = "1234567893"
    presc = "1245319599"
    for i in range(10):
        db.add(FlaggedClaim(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a_id,
            auth_number=f"AUTH-{i:04d}",
            date_of_service=date.today(),
            pharmacy_npi=pharm,
            prescriber_npi=presc,
            member_id=f"MEMBER-{i:03d}",
            rule_code="RULE_TEST",
            rule_name="test ring fixture",
            detection_mode="rule",
            risk_score=50,
            confidence_tier="medium",
            severity="medium",
            evidence={},
            billed_amount=Decimal("100.00"),
            investigation_status="open",
        ))
    db.flush()

def test_graph_job_real_computation_e2e(db, tenant_a_id, dense_pharmacy_prescriber_ring):
    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-1")

    assert isinstance(result, dict)
    assert set(result.keys()) == {"rings", "investigations", "records"}
    assert isinstance(result["rings"], list)
    assert result["records"] == 10

    assert len(result["rings"]) >= 1
    ring = result["rings"][0]
    assert isinstance(ring["density_score"], Decimal)
    assert ring["node_count"] >= 3
    assert ring["edge_count"] >= 1
    assert isinstance(ring["entity_refs"], list)
    assert len(ring["entity_refs"]) <= 500
    for ref in ring["entity_refs"]:
        assert "type" in ref and "id" in ref
        assert ref["type"] in {"pharmacy", "prescriber", "member"}


def test_graph_job_returns_empty_when_no_flagged_claims(db, tenant_a_id):
    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-empty")
    assert result == {"rings": [], "investigations": 0, "records": 0}


def test_graph_job_skips_rows_missing_triple_fields(db, tenant_a_id):
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-COMPLETE",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi="1245319599",
        member_id="MEMBER-001",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-MISSING-PRESC",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi=None,
        member_id="MEMBER-002",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.flush()

    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-filter")
    assert result["records"] == 1


def test_graph_job_aggregates_duplicate_triples(db, tenant_a_id):
    pharm, presc, member = "1234567893", "1245319599", "MEMBER-001"
    for i in range(3):
        db.add(FlaggedClaim(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a_id,
            auth_number=f"AUTH-AGG-{i:04d}",
            date_of_service=date.today(),
            pharmacy_npi=pharm,
            prescriber_npi=presc,
            member_id=member,
            rule_code="R", rule_name="r", detection_mode="rule",
            risk_score=50, confidence_tier="medium", severity="medium",
            evidence={}, billed_amount=Decimal("50.00"),
            investigation_status="open",
        ))
    db.flush()

    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-agg")
    assert result["records"] == 3


def test_graph_job_handles_null_billed_amount(db, tenant_a_id):
    """FlaggedClaim with NULL billed_amount still counts as a record."""
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-NULL-BILL",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi="1245319599",
        member_id="MEMBER-NULLBILL",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=None,
        investigation_status="open",
    ))
    db.flush()

    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-null-bill")
    assert result["records"] == 1  # row is counted even with null billed_amount


def test_non_suspicious_community_produces_no_ring(db, tenant_a_id):
    """When FraudNetworkAnalyzer returns non-suspicious communities, rings list is empty."""
    from unittest.mock import patch, MagicMock
    from src.services.graph_analysis import CommunityResult
    from decimal import Decimal

    # Seed a single claim (1 pharm + 1 presc + 1 member)
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-NON-SUSP",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi="1245319599",
        member_id="MEMBER-NONSUSP",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.flush()

    non_suspicious = CommunityResult(
        community_id=0,
        nodes=["pharmacy:1234567893", "prescriber:1245319599", "member:MEMBER-NONSUSP"],
        pharmacies=["1234567893"],
        prescribers=["1245319599"],
        members=["MEMBER-NONSUSP"],
        total_claims=1,
        total_amount=Decimal("100"),
        self_referral_rate=0.3,  # below suspicious threshold
        geographic_spread_score=1.0,
        is_suspicious=False,
        suspicion_reasons=[],
    )

    job = GraphAnalysisJob(db)
    from src.services.graph_analysis import FraudNetworkAnalyzer
    with patch.object(FraudNetworkAnalyzer, "detect_communities", return_value=[non_suspicious]):
        result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-non-susp")

    assert result["rings"] == []
    assert result["investigations"] == 0
    assert result["records"] == 1


def test_low_density_ring_not_counted_as_investigation(db, tenant_a_id):
    """Ring with density_score < 0.80 is detected but no investigation opened."""
    from unittest.mock import patch
    from src.services.graph_analysis import CommunityResult
    from decimal import Decimal

    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-LOW-DENSITY",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi="1245319599",
        member_id="MEMBER-LOWDENS",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.flush()

    low_density = CommunityResult(
        community_id=0,
        nodes=["pharmacy:1234567893", "prescriber:1245319599", "member:MEMBER-LOWDENS"],
        pharmacies=["1234567893"],
        prescribers=["1245319599"],
        members=["MEMBER-LOWDENS"],
        total_claims=1,
        total_amount=Decimal("100"),
        self_referral_rate=0.5,  # suspicious but below density threshold 0.80
        geographic_spread_score=1.0,
        is_suspicious=True,  # ring detected
        suspicion_reasons=["test"],
    )

    job = GraphAnalysisJob(db)
    from src.services.graph_analysis import FraudNetworkAnalyzer
    with patch.object(FraudNetworkAnalyzer, "detect_communities", return_value=[low_density]):
        result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-low-dens")

    assert len(result["rings"]) == 1
    assert result["rings"][0]["density_score"] < Decimal("0.80")
    assert result["investigations"] == 0  # no investigation opened for low density
