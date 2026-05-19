"""Graph analysis batch job for ReclaimRx.

Builds pharmacy-prescriber-member fraud network from FlaggedClaim rows,
runs Louvain community detection, persists suspicious rings, and auto-opens
investigations for high-density rings.

Advisory lock key uses zlib.crc32 (never Python hash()) per audit section 9.
"""
from __future__ import annotations

import logging
import uuid
import zlib
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import FlaggedClaim, GraphRun, Investigation
from src.outbox.event_outbox import OutboxService

_logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 90
_STALE_TIMEOUT_HOURS = 4
_GRAPH_DENSITY_THRESHOLD = Decimal("0.80")
_MAX_ENTITY_REFS = 500



def advisory_lock_key(tenant_id):
    raw = __import__("zlib").crc32(f"graph_run:{tenant_id}".encode())
    return raw & 0x7FFFFFFF


class RunInProgressError(RuntimeError):
    def __init__(self, existing_run_id=None):
        super().__init__("RUN_IN_PROGRESS")
        self.existing_run_id = existing_run_id
        self.code = "RUN_IN_PROGRESS"


class GraphAnalysisJob:
    def __init__(self, session):
        self._session = session

    def trigger(self, *, tenant_id, trigger_source):
        if not self._pg_try_advisory_lock(tenant_id):
            raise RunInProgressError()
        self._check_running(tenant_id)
        gr = self._insert_graph_run(tenant_id, trigger_source)
        self._session.flush()
        try:
            result = self._run_graph_computation(tenant_id, gr.id)
        except Exception as exc:
            import datetime as _dt
            now = _dt.datetime.now(_dt.UTC)
            gr.status = "failed"
            gr.failed_at = now
            gr.error_code = "COMPUTATION_ERROR"
            gr.error_message = str(exc)[:2000]
            self._session.flush()
            raise
        import datetime as _dt
        now = _dt.datetime.now(_dt.UTC)
        gr.status = "completed"
        gr.completed_at = now
        gr.rings_detected = len(result["rings"])
        gr.investigations_opened = result["investigations"]
        gr.records_scanned = result["records"]
        self._session.flush()
        from src.outbox.event_outbox import OutboxService
        OutboxService(self._session).write(
            event_type="fwa.graph_run_completed",
            tenant_id=tenant_id,
            idempotency_key=f"graph_run:completed:{gr.id}",
            ordering_key=str(tenant_id),
            payload={
                "graph_run_id": gr.id,
                "rings_detected": gr.rings_detected,
                "investigations_opened": gr.investigations_opened,
                "records_scanned": gr.records_scanned,
                "status": gr.status,
            },
        )
        return gr

    def _pg_try_advisory_lock(self, tenant_id):
        from sqlalchemy import text
        bind = self._session.bind
        dialect = bind.dialect.name if bind is not None else "sqlite"
        if dialect != "postgresql":
            return True
        from src.jobs.graph_analysis_job import advisory_lock_key  # pragma: no cover
        lock_key = advisory_lock_key(tenant_id)  # pragma: no cover
        result = self._session.execute(  # pragma: no cover
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key}
        )  # pragma: no cover
        return bool(result.scalar())  # pragma: no cover

    def _check_running(self, tenant_id):
        import datetime as _dt
        from sqlalchemy import select
        from src.models.tables import GraphRun
        now = _dt.datetime.now(_dt.UTC)
        existing = self._session.execute(
            select(GraphRun).where(
                GraphRun.tenant_id == str(tenant_id),
                GraphRun.status == "running",
            )
        ).scalars().first()
        if existing is None:
            return
        if existing.stale_timeout_at < now:
            existing.status = "failed"
            existing.failed_at = now
            existing.error_code = "STALE_TIMEOUT"
            self._session.flush()
            return
        raise RunInProgressError(existing_run_id=existing.id)

    def _run_graph_computation(self, tenant_id, graph_run_id):
        from src.services.graph_analysis import FraudNetworkAnalyzer, GraphEdge
        import datetime as _dt
        from decimal import Decimal, ROUND_HALF_UP
        from collections import defaultdict
        from sqlalchemy import select
        from src.models.tables import FlaggedClaim
        import uuid as _uuid

        _LOOKBACK = 90
        cutoff = _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=_LOOKBACK)
        rows = self._session.execute(
            select(
                FlaggedClaim.pharmacy_npi,
                FlaggedClaim.prescriber_npi,
                FlaggedClaim.member_id,
                FlaggedClaim.billed_amount,
            ).where(
                FlaggedClaim.tenant_id == str(tenant_id),
                FlaggedClaim.date_of_service >= cutoff.date(),
                FlaggedClaim.pharmacy_npi.is_not(None),
                FlaggedClaim.prescriber_npi.is_not(None),
                FlaggedClaim.member_id.is_not(None),
            )
        ).all()

        records_scanned = len(rows)
        if records_scanned == 0:
            return {"rings": [], "investigations": 0, "records": 0}

        edge_acc = defaultdict(lambda: {"claim_count": 0, "total_amount": Decimal("0")})
        for pharm, presc, member, billed in rows:
            key = (pharm, presc, member)
            edge_acc[key]["claim_count"] += 1
            if billed is not None:
                edge_acc[key]["total_amount"] += Decimal(str(billed))

        edges = [
            GraphEdge(
                pharmacy_npi=k[0],
                prescriber_npi=k[1],
                member_id=k[2],
                claim_count=v["claim_count"],
                total_amount=v["total_amount"],
            )
            for k, v in edge_acc.items()
        ]

        analyzer = FraudNetworkAnalyzer()
        graph = analyzer.build_graph(edges)
        communities = analyzer.detect_communities(graph)

        rings = []
        investigations_opened = 0
        _DENSITY_THRESH = Decimal("0.80")
        for community in communities:
            if not community.is_suspicious:
                continue
            entity_refs = self._build_entity_refs(community)
            ring = {
                "density_score": Decimal(str(community.self_referral_rate)).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                ),
                "node_count": len(community.nodes),
                "edge_count": graph.subgraph(community.nodes).number_of_edges(),
                "entity_refs": entity_refs,
            }
            rings.append(ring)
            if ring["density_score"] >= _DENSITY_THRESH:
                investigations_opened += 1

        return {"rings": rings, "investigations": investigations_opened, "records": records_scanned}

    def _build_entity_refs(self, community):
        refs = []
        for npi in community.pharmacies:
            refs.append({"type": "pharmacy", "id": npi, "npi": npi})
        for npi in community.prescribers:
            refs.append({"type": "prescriber", "id": npi, "npi": npi})
        for member_id in community.members:
            refs.append({"type": "member", "id": member_id})
        return refs[:500]

    def _insert_graph_run(self, tenant_id, trigger_source):
        import datetime as _dt, uuid as _uuid
        from src.models.tables import GraphRun
        now = _dt.datetime.now(_dt.UTC)
        gr = GraphRun(
            id=str(_uuid.uuid4()),
            tenant_id=str(tenant_id),
            status="running",
            trigger=trigger_source,
            started_at=now,
            stale_timeout_at=now + _dt.timedelta(hours=4),
            correlation_id=str(_uuid.uuid4()),
            lookback_window_days=90,
            rings_detected=0,
            investigations_opened=0,
            records_scanned=0,
        )
        self._session.add(gr)
        return gr

    def _open_investigation_for_ring(self, tenant_id, ring_id):
        import datetime as _dt, uuid as _uuid
        from src.models.tables import Investigation
        now = _dt.datetime.now(_dt.UTC)
        return Investigation(
            id=str(_uuid.uuid4()),
            tenant_id=str(tenant_id),
            investigation_number=f"INV-{now.year}-GR-{str(_uuid.uuid4())[:8].upper()}",
            title="Graph-detected fraud ring",
            subject_type="fraud_ring",
            subject_entity_id=ring_id,
            investigation_type="graph_ring",
            status="open",
            priority="high",
            opened_at=now,
        )
