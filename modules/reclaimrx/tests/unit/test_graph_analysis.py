"""Tests for NetworkX community detection — TDD first."""
from __future__ import annotations

from decimal import Decimal

from src.services.graph_analysis import (
    CommunityResult,
    FraudNetworkAnalyzer,
    GraphEdge,
)


def make_edge(
    pharmacy: str,
    prescriber: str,
    member: str,
    claim_count: int = 5,
    amount: Decimal | str | int | float = "500.00",
) -> GraphEdge:
    return GraphEdge(
        pharmacy_npi=pharmacy,
        prescriber_npi=prescriber,
        member_id=member,
        claim_count=claim_count,
        total_amount=amount if isinstance(amount, Decimal) else Decimal(str(amount)),
    )


class TestFraudNetworkAnalyzer:
    def test_builds_graph_from_edges(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        edges = [
            make_edge("P001", "DR001", "MEM001"),
            make_edge("P001", "DR001", "MEM002"),
            make_edge("P002", "DR002", "MEM003"),
        ]
        graph = analyzer.build_graph(edges)
        assert graph.number_of_nodes() >= 3
        assert graph.number_of_edges() >= 3

    def test_detects_communities(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        edges = [
            make_edge("P001", "DR001", "MEM001", 100, 5000.0),
            make_edge("P001", "DR001", "MEM002", 100, 5000.0),
            make_edge("P001", "DR001", "MEM003", 100, 5000.0),
            make_edge("P002", "DR002", "MEM004", 5, 200.0),
        ]
        graph = analyzer.build_graph(edges)
        communities = analyzer.detect_communities(graph)
        assert isinstance(communities, list)
        assert len(communities) >= 1

    def test_community_result_has_required_fields(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        edges = [
            make_edge("P001", "DR001", "MEM001", 50, 2500.0),
            make_edge("P001", "DR001", "MEM002", 50, 2500.0),
        ]
        graph = analyzer.build_graph(edges)
        communities = analyzer.detect_communities(graph)
        if communities:
            comm = communities[0]
            assert isinstance(comm, CommunityResult)
            assert hasattr(comm, "nodes")
            assert hasattr(comm, "self_referral_rate")
            assert hasattr(comm, "is_suspicious")

    def test_suspicious_community_high_self_referral(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        # Tight cluster: one pharmacy, one prescriber, many members
        edges = [make_edge("P001", "DR001", f"MEM{i:03d}", 20, 1000.0) for i in range(20)]
        # Add sparse connections to other entities
        edges.append(make_edge("P002", "DR003", "MEM999", 1, 50.0))
        graph = analyzer.build_graph(edges)
        communities = analyzer.detect_communities(graph)
        suspicious = [c for c in communities if c.is_suspicious]
        assert len(suspicious) >= 1

    def test_entity_relationship_map(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        edges = [
            make_edge("P001", "DR001", "MEM001"),
            make_edge("P001", "DR002", "MEM001"),
            make_edge("P002", "DR001", "MEM002"),
        ]
        graph = analyzer.build_graph(edges)
        neighbors = analyzer.get_entity_neighbors(graph, entity_type="pharmacy", entity_id="P001")
        assert len(neighbors) >= 2

    def test_empty_edges_returns_empty_communities(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        graph = analyzer.build_graph([])
        communities = analyzer.detect_communities(graph)
        assert communities == []

    def test_get_entity_neighbors_unknown_entity_returns_empty(self) -> None:
        analyzer = FraudNetworkAnalyzer()
        edges = [make_edge("P001", "DR001", "MEM001")]
        graph = analyzer.build_graph(edges)
        neighbors = analyzer.get_entity_neighbors(graph, entity_type="pharmacy", entity_id="UNKNOWN")
        assert neighbors == []
