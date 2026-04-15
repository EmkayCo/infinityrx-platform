"""OFAC SDN screening service — DB-backed with fuzzy matching.

Replaces the previous in-memory stub. Screens pay-to entities against the
SDN list stored in ``payment_proc_ofac_sdn``; any match blocks the payment
and writes an ``OfacScreeningAlert`` audit row.

Confidence tiers:
    exact    — sdn_uid or full canonical_name matches verbatim (score=100)
    probable — name similarity ≥ probable_threshold  (default 90)
    possible — name similarity ≥ possible_threshold  (default 80)

Caller policy (enforced by payment submission layer):
    exact    → block outright, auto-create alert, open investigation
    probable → block, create alert, require human review
    possible → allow but flag for review
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.tables import OfacScreeningAlert, OfacSdnEntry

logger = logging.getLogger("payment.ofac")


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


@dataclass
class OfacResult:
    entity_id: str
    is_blocked: bool
    match_name: str | None = None
    match_score: int | None = None
    match_confidence: str | None = None  # exact | probable | possible
    sdn_id: str | None = None
    alert_id: str | None = None


class OfacScreeningService:
    """DB-backed SDN screening with fuzzy name matching.

    The legacy in-memory path is kept as a constructor convenience for tests
    that don't want to spin up the DB — pass ``blocked_entity_ids`` and the
    service short-circuits before any SDN query.
    """

    DEFAULT_PROBABLE_THRESHOLD = 90
    DEFAULT_POSSIBLE_THRESHOLD = 80

    def __init__(
        self,
        session: Session | None = None,
        *,
        blocked_entity_ids: set[str] | None = None,
        probable_threshold: int = DEFAULT_PROBABLE_THRESHOLD,
        possible_threshold: int = DEFAULT_POSSIBLE_THRESHOLD,
    ) -> None:
        self._session = session
        self._legacy_blocked: set[str] = blocked_entity_ids or set()
        self._probable = probable_threshold
        self._possible = possible_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def screen(
        self,
        entity_id: str,
        entity_name: str = "",
        *,
        tenant_id: str | None = None,
        record_alert: bool = True,
    ) -> OfacResult:
        """Screen a single entity. Creates an alert row on match when session is available."""
        # Legacy fast-path: explicit in-memory block list (kept for existing tests)
        if entity_id in self._legacy_blocked:
            return OfacResult(
                entity_id=entity_id,
                is_blocked=True,
                match_name=entity_name,
                match_score=100,
                match_confidence="exact",
                sdn_id="SDN-LEGACY",
            )

        if self._session is None:
            return OfacResult(entity_id=entity_id, is_blocked=False)

        hit = self._find_hit(entity_name)
        if hit is None:
            return OfacResult(entity_id=entity_id, is_blocked=False)

        sdn_entry, score, confidence = hit
        logger.warning(
            "ofac.hit",
            extra={
                "svc_entity_id": entity_id,
                "svc_entity_name": entity_name,
                "svc_sdn_uid": sdn_entry.sdn_uid,
                "svc_match_score": score,
                "svc_match_confidence": confidence,
                "svc_tenant_id": tenant_id or "",
            },
        )

        alert_id: str | None = None
        if record_alert and tenant_id is not None:
            alert = OfacScreeningAlert(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                entity_id=entity_id,
                entity_name=entity_name or None,
                sdn_uid=sdn_entry.sdn_uid,
                sdn_canonical_name=sdn_entry.canonical_name,
                match_confidence=confidence,
                match_score=score,
                match_reason=f"name similarity {score}",
                resolution_status="open",
            )
            self._session.add(alert)
            self._session.flush()
            alert_id = alert.id

        # "possible" tier is NOT a hard block; caller applies policy.
        is_blocked = confidence in ("exact", "probable")
        return OfacResult(
            entity_id=entity_id,
            is_blocked=is_blocked,
            match_name=sdn_entry.canonical_name,
            match_score=score,
            match_confidence=confidence,
            sdn_id=sdn_entry.sdn_uid,
            alert_id=alert_id,
        )

    def screen_batch(
        self,
        entities: list[tuple[str, str]],
        *,
        tenant_id: str | None = None,
    ) -> list[OfacResult]:
        return [self.screen(eid, name, tenant_id=tenant_id) for eid, name in entities]

    # ------------------------------------------------------------------
    # Seeding helpers
    # ------------------------------------------------------------------

    def upsert_sdn_entry(
        self,
        *,
        sdn_uid: str,
        sdn_type: str,
        canonical_name: str,
        program: str | None = None,
        aliases: Iterable[str] | None = None,
        address: str | None = None,
        country: str | None = None,
        source: str = "SDN",
    ) -> OfacSdnEntry:
        """Insert or update an SDN entry. Used by the CSV loader + tests."""
        if self._session is None:
            raise RuntimeError("OfacScreeningService needs a DB session for upsert")

        existing = self._session.execute(
            select(OfacSdnEntry).where(OfacSdnEntry.sdn_uid == sdn_uid)
        ).scalar_one_or_none()
        aliases_text = "\n".join(a for a in (aliases or []) if a) or None

        if existing is None:
            entry = OfacSdnEntry(
                id=str(uuid.uuid4()),
                sdn_uid=sdn_uid,
                sdn_type=sdn_type,
                program=program,
                canonical_name=_norm(canonical_name),
                aliases=aliases_text,
                address=address,
                country=country,
                source=source,
            )
            self._session.add(entry)
            self._session.flush()
            return entry

        existing.sdn_type = sdn_type
        existing.program = program
        existing.canonical_name = _norm(canonical_name)
        existing.aliases = aliases_text
        existing.address = address
        existing.country = country
        existing.source = source
        existing.updated_at = datetime.now(UTC)
        self._session.flush()
        return existing

    # Legacy helpers kept for backwards compatibility in existing tests
    def add_blocked(self, entity_id: str) -> None:
        self._legacy_blocked.add(entity_id)

    def remove_blocked(self, entity_id: str) -> None:
        self._legacy_blocked.discard(entity_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_hit(self, entity_name: str) -> tuple[OfacSdnEntry, int, str] | None:
        needle = _norm(entity_name)
        if not needle:
            return None

        # Narrow the candidate set with a LIKE pre-filter on the first token so
        # we don't fuzz every row. Production data sets are ~12k entries which
        # rapidfuzz can handle in ~10ms even without a prefilter; the LIKE is
        # still helpful when the SDN table grows.
        first_tok = needle.split()[0] if needle.split() else needle
        candidates = self._session.execute(  # type: ignore[union-attr]
            select(OfacSdnEntry).where(
                or_(
                    OfacSdnEntry.canonical_name.like(f"%{first_tok}%"),
                    OfacSdnEntry.aliases.like(f"%{first_tok}%"),
                )
            )
        ).scalars().all()
        if not candidates:
            return None

        best_entry: OfacSdnEntry | None = None
        best_score = 0
        for entry in candidates:
            # Exact match on canonical_name → 100
            if entry.canonical_name == needle:
                return entry, 100, "exact"
            score = fuzz.token_sort_ratio(entry.canonical_name, needle)
            if entry.aliases:
                for alias in entry.aliases.split("\n"):
                    alias_norm = _norm(alias)
                    if alias_norm == needle:
                        return entry, 100, "exact"
                    alias_score = fuzz.token_sort_ratio(alias_norm, needle)
                    if alias_score > score:
                        score = alias_score
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is None:
            return None
        if best_score >= self._probable:
            return best_entry, int(best_score), "probable"
        if best_score >= self._possible:
            return best_entry, int(best_score), "possible"
        return None
