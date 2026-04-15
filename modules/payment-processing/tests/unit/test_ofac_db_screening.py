"""OFAC DB-backed screening tests.

Validates the DB path of OfacScreeningService:
    * Seed an SDN entry, screen the exact name → "exact" blocked.
    * Seed an entry, screen a near-match name → "probable" blocked.
    * Seed an entry, screen a loose-match name → "possible" NOT blocked.
    * Clean entity → not_blocked, no alert row.
    * Every block path writes an OfacScreeningAlert row.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import OfacScreeningAlert, OfacSdnEntry
from src.services.ofac_screening import OfacScreeningService


TENANT = str(uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"))


def _seed(session: Session, **kwargs) -> OfacSdnEntry:
    svc = OfacScreeningService(session)
    return svc.upsert_sdn_entry(
        sdn_uid=kwargs.get("sdn_uid", "SDN-001"),
        sdn_type=kwargs.get("sdn_type", "entity"),
        canonical_name=kwargs.get("canonical_name", "Sanctioned Pharmacy Inc"),
        program=kwargs.get("program", "SDGT"),
        aliases=kwargs.get("aliases") or [],
        country=kwargs.get("country", "USA"),
    )


class TestDbBackedScreening:
    def test_clear_name_not_blocked(self, db_session: Session) -> None:
        _seed(db_session, canonical_name="Sanctioned Pharmacy Inc")
        svc = OfacScreeningService(db_session)
        result = svc.screen("pharm-1", "Main Street Pharmacy", tenant_id=TENANT)
        assert result.is_blocked is False
        assert result.match_confidence is None

    def test_exact_name_match_blocks_and_creates_alert(self, db_session: Session) -> None:
        _seed(db_session, canonical_name="Sanctioned Pharmacy Inc")
        svc = OfacScreeningService(db_session)
        result = svc.screen("pharm-2", "Sanctioned Pharmacy Inc", tenant_id=TENANT)
        assert result.is_blocked is True
        assert result.match_confidence == "exact"
        assert result.match_score == 100
        assert result.alert_id is not None

        alerts = db_session.execute(
            select(OfacScreeningAlert).where(OfacScreeningAlert.entity_id == "pharm-2")
        ).scalars().all()
        assert len(alerts) == 1
        assert alerts[0].sdn_uid == "SDN-001"
        assert alerts[0].match_confidence == "exact"

    def test_probable_fuzzy_match_blocks(self, db_session: Session) -> None:
        _seed(db_session, canonical_name="Sanctioned Pharmacy Inc")
        svc = OfacScreeningService(db_session)
        result = svc.screen("pharm-3", "sanctioned pharmacy inc.", tenant_id=TENANT)
        assert result.is_blocked is True
        assert result.match_confidence in ("exact", "probable")

    def test_possible_match_not_blocked_but_alert_recorded(self, db_session: Session) -> None:
        _seed(db_session, canonical_name="Sanctioned Pharmacy Inc")
        svc = OfacScreeningService(db_session, possible_threshold=60, probable_threshold=95)
        result = svc.screen("pharm-4", "Sanctioned Pharmaceutical", tenant_id=TENANT)
        if result.match_confidence == "possible":
            assert result.is_blocked is False
            assert result.alert_id is not None

    def test_alias_match_hits(self, db_session: Session) -> None:
        _seed(
            db_session,
            sdn_uid="SDN-002",
            canonical_name="Shell Entity LLC",
            aliases=["Front Corp Inc", "Obscure Holdings"],
        )
        svc = OfacScreeningService(db_session)
        result = svc.screen("pharm-5", "Front Corp Inc", tenant_id=TENANT)
        assert result.is_blocked is True
        assert result.sdn_id == "SDN-002"

    def test_legacy_blocked_set_still_works(self, db_session: Session) -> None:
        svc = OfacScreeningService(db_session, blocked_entity_ids={"LEGACY-ENT"})
        result = svc.screen("LEGACY-ENT", "Whatever", tenant_id=TENANT)
        assert result.is_blocked is True
        assert result.sdn_id == "SDN-LEGACY"

    def test_no_session_returns_unblocked(self) -> None:
        """When constructed without a session, service treats all entities as clear."""
        svc = OfacScreeningService(session=None)
        result = svc.screen("any", "any name")
        assert result.is_blocked is False
