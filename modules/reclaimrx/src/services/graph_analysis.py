"""NetworkX community detection for pharmacy-prescriber-member fraud rings.

Uses Louvain algorithm to detect suspicious communities in claim relationships.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import networkx as nx

try:
    from community import best_partition  # python-louvain  # pragma: no cover
    HAS_LOUVAIN = True  # pragma: no cover
except ImportError:
    HAS_LOUVAIN = False


_ZERO = Decimal("0")


@dataclass
class GraphEdge:
    """An edge in the fraud detection graph (claim relationship).

    ``total_amount`` is a Decimal because graph accumulation across many
    edges would otherwise drift via IEEE 754 float error, and the value is
    published onto the event bus into downstream financial consumers.
    """

    pharmacy_npi: str
    prescriber_npi: str
    member_id: str
    claim_count: int = 1
    total_amount: Decimal = field(default_factory=lambda: _ZERO)


@dataclass
class CommunityResult:
    """Result of community detection for a cluster of entities.

    ``total_amount`` is a Decimal (aggregated dollars). ``self_referral_rate``
    and ``geographic_spread_score`` are ratios/scores, not money — float is
    appropriate for those.
    """

    community_id: int
    nodes: list[str]
    pharmacies: list[str]
    prescribers: list[str]
    members: list[str]
    total_claims: int
    total_amount: Decimal
    self_referral_rate: float
    geographic_spread_score: float
    is_suspicious: bool
    suspicion_reasons: list[str] = field(default_factory=list)


# Suspicion thresholds (matching PRD ALL-008)
SUSPICIOUS_SELF_REFERRAL_RATE = 0.80
SUSPICIOUS_MIN_NODES = 3


class FraudNetworkAnalyzer:
    """Builds and analyzes pharmacy-prescriber-member relationship graphs."""

    def build_graph(self, edges: list[GraphEdge]) -> nx.Graph:
        """Build a weighted undirected graph from claim edges."""
        G = nx.Graph()
        for edge in edges:
            pharm_node = f"pharmacy:{edge.pharmacy_npi}"
            presc_node = f"prescriber:{edge.prescriber_npi}"
            member_node = f"member:{edge.member_id}"

            # Add nodes with type metadata
            G.add_node(pharm_node, entity_type="pharmacy", entity_id=edge.pharmacy_npi)
            G.add_node(presc_node, entity_type="prescriber", entity_id=edge.prescriber_npi)
            G.add_node(member_node, entity_type="member", entity_id=edge.member_id)

            # Add/update edges with aggregated weight
            self._add_or_update_edge(G, pharm_node, presc_node, edge)
            self._add_or_update_edge(G, presc_node, member_node, edge)
            self._add_or_update_edge(G, pharm_node, member_node, edge)

        return G

    def _add_or_update_edge(self, G: nx.Graph, u: str, v: str, edge: GraphEdge) -> None:
        if G.has_edge(u, v):
            G[u][v]["weight"] += edge.claim_count
            G[u][v]["total_amount"] = G[u][v]["total_amount"] + edge.total_amount
        else:
            G.add_edge(u, v, weight=edge.claim_count, total_amount=edge.total_amount)

    def detect_communities(self, G: nx.Graph) -> list[CommunityResult]:
        """Detect communities using Louvain algorithm (or greedy modularity fallback)."""
        if G.number_of_nodes() == 0:
            return []

        if HAS_LOUVAIN and G.number_of_nodes() > 1:  # pragma: no cover
            partition = best_partition(G)  # pragma: no cover
        else:
            # Fallback: greedy modularity communities
            try:
                communities_gen = nx.algorithms.community.greedy_modularity_communities(G)
                community_list = list(communities_gen)
                partition = {}
                for idx, community_nodes in enumerate(community_list):
                    for node in community_nodes:
                        partition[node] = idx
            except Exception:  # pragma: no cover
                # Last resort: each node is its own community
                partition = {node: i for i, node in enumerate(G.nodes())}  # pragma: no cover

        # Group nodes by community
        community_groups: dict[int, list[str]] = {}
        for node, comm_id in partition.items():
            community_groups.setdefault(comm_id, []).append(node)

        results = []
        for comm_id, nodes in community_groups.items():
            result = self._analyze_community(G, comm_id, nodes)
            results.append(result)

        return results

    def _analyze_community(self, G: nx.Graph, comm_id: int, nodes: list[str]) -> CommunityResult:
        pharmacies = [G.nodes[n]["entity_id"] for n in nodes if G.nodes[n].get("entity_type") == "pharmacy"]
        prescribers = [G.nodes[n]["entity_id"] for n in nodes if G.nodes[n].get("entity_type") == "prescriber"]
        members = [G.nodes[n]["entity_id"] for n in nodes if G.nodes[n].get("entity_type") == "member"]

        # Calculate internal edges (within community)
        node_set = set(nodes)
        total_weight = 0
        internal_weight = 0
        total_amount: Decimal = _ZERO

        for u, v, data in G.edges(data=True):
            w = data.get("weight", 1)
            amt = data.get("total_amount", _ZERO)
            total_weight += w
            total_amount = total_amount + amt
            if u in node_set and v in node_set:
                internal_weight += w

        self_referral_rate = (internal_weight / total_weight) if total_weight > 0 else 0.0
        total_claims = internal_weight

        # Geographic spread (placeholder — in production, use actual geo data)
        geographic_spread_score = float(len(set(pharmacies + prescribers)))

        is_suspicious, reasons = self._assess_suspicion(
            nodes, pharmacies, prescribers, members,
            self_referral_rate, total_claims, total_amount
        )

        return CommunityResult(
            community_id=comm_id,
            nodes=nodes,
            pharmacies=pharmacies,
            prescribers=prescribers,
            members=members,
            total_claims=total_claims,
            total_amount=total_amount,
            self_referral_rate=self_referral_rate,
            geographic_spread_score=geographic_spread_score,
            is_suspicious=is_suspicious,
            suspicion_reasons=reasons,
        )

    def _assess_suspicion(
        self,
        nodes: list[str],
        pharmacies: list[str],
        prescribers: list[str],
        members: list[str],
        self_referral_rate: float,
        total_claims: int,
        total_amount: Decimal,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if self_referral_rate >= SUSPICIOUS_SELF_REFERRAL_RATE and len(nodes) >= SUSPICIOUS_MIN_NODES:
            reasons.append(
                f"High self-referral rate ({self_referral_rate:.0%}) among {len(nodes)} entities"
            )

        if len(pharmacies) == 1 and len(prescribers) == 1 and len(members) > 5:
            reasons.append(
                f"Single pharmacy-prescriber pair routing {len(members)} members"
            )

        return bool(reasons), reasons

    def get_entity_neighbors(
        self,
        G: nx.Graph,
        *,
        entity_type: str,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Get all entities connected to a given entity."""
        node_key = f"{entity_type}:{entity_id}"
        if node_key not in G:
            return []

        neighbors = []
        for neighbor in G.neighbors(node_key):
            edge_data = G.get_edge_data(node_key, neighbor, {})
            node_data = G.nodes[neighbor]
            neighbors.append({
                "entity_type": node_data.get("entity_type"),
                "entity_id": node_data.get("entity_id"),
                "claim_count": edge_data.get("weight", 0),
                "total_amount": edge_data.get("total_amount", _ZERO),
            })
        return neighbors
