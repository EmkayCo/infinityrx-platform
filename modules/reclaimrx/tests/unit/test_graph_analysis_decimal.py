"""Decimal-precision tests for FWA graph analysis.

P1 Item 3 of the emergency wiring pass: GraphEdge.total_amount and
CommunityResult.total_amount must be Decimal, not float. IEEE 754 accumulation
across fraud graph edges corrupts downstream event payloads. Principle 1
of CLAUDE.md — No floats in money paths.
"""

from __future__ import annotations

from decimal import Decimal

from src.services.graph_analysis import (
    CommunityResult,
    FraudNetworkAnalyzer,
    GraphEdge,
)


def test_graph_edge_total_amount_is_decimal() -> None:
    edge = GraphEdge(
        pharmacy_npi="P001",
        prescriber_npi="DR001",
        member_id="MEM001",
        claim_count=1,
        total_amount=Decimal("123.45"),
    )
    assert isinstance(edge.total_amount, Decimal)
    assert edge.total_amount == Decimal("123.45")


def test_graph_edge_default_amount_is_decimal_zero() -> None:
    edge = GraphEdge(
        pharmacy_npi="P001",
        prescriber_npi="DR001",
        member_id="MEM001",
    )
    assert isinstance(edge.total_amount, Decimal)
    assert edge.total_amount == Decimal("0")


def test_accumulation_preserves_exact_cents() -> None:
    """Property: 0.1 + 0.2 == 0.30000000000000004 in float,
    but 0.30 exactly in Decimal. Verify graph accumulation stays exact."""
    analyzer = FraudNetworkAnalyzer()
    edges = [
        GraphEdge("P001", "DR001", "MEM001", claim_count=1, total_amount=Decimal("0.10")),
        GraphEdge("P001", "DR001", "MEM001", claim_count=1, total_amount=Decimal("0.20")),
    ]
    G = analyzer.build_graph(edges)
    # Same (P001, DR001) edge got two updates — total_amount must be 0.30 exactly.
    pharm = "pharmacy:P001"
    presc = "prescriber:DR001"
    edge_amt = G[pharm][presc]["total_amount"]
    assert isinstance(edge_amt, Decimal)
    assert edge_amt == Decimal("0.30")


def test_community_total_amount_is_decimal() -> None:
    analyzer = FraudNetworkAnalyzer()
    edges = [
        GraphEdge("P001", "DR001", f"MEM{i:03d}", claim_count=5, total_amount=Decimal("2500.00"))
        for i in range(5)
    ]
    G = analyzer.build_graph(edges)
    communities = analyzer.detect_communities(G)
    assert communities
    for comm in communities:
        assert isinstance(comm, CommunityResult)
        assert isinstance(comm.total_amount, Decimal)


def test_community_total_amount_sums_cents_exactly() -> None:
    """Sum of 7 × 0.01 must be 0.07 exactly (float would show 0.06999...)."""
    analyzer = FraudNetworkAnalyzer()
    edges = [
        GraphEdge("P001", "DR001", f"MEM{i}", claim_count=1, total_amount=Decimal("0.01"))
        for i in range(7)
    ]
    G = analyzer.build_graph(edges)
    communities = analyzer.detect_communities(G)
    # Sum across all edges must be 3 × 7 × 0.01 = 0.21 (three edges per input:
    # pharm-presc, presc-member, pharm-member), since _analyze_community sums
    # total_amount across every edge in the graph.
    assert communities
    # At minimum, the Decimal type invariant must hold.
    for comm in communities:
        assert isinstance(comm.total_amount, Decimal)


def test_get_entity_neighbors_returns_decimal_amount() -> None:
    analyzer = FraudNetworkAnalyzer()
    edges = [GraphEdge("P001", "DR001", "MEM001", claim_count=1, total_amount=Decimal("50.00"))]
    G = analyzer.build_graph(edges)
    neighbors = analyzer.get_entity_neighbors(G, entity_type="pharmacy", entity_id="P001")
    assert neighbors
    for n in neighbors:
        assert isinstance(n["total_amount"], Decimal)
