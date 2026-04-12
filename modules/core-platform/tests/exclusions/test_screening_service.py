from __future__ import annotations

import pytest

from src._shim import events as events_shim
from src._shim.notifications import NotificationService
from src.exclusions.matching import MatchCandidate
from src.exclusions.screening_service import (
    EVENT_ENTITY_BLOCKED,
    EVENT_MATCH_FOUND,
    ExclusionScreeningService,
    TenantScreeningConfig,
)
from src.models import ExclusionListEntry, ExclusionMatch


@pytest.fixture
def seeded(db_session):
    db_session.add(
        ExclusionListEntry(
            source="OIG",
            entity_type="individual",
            npi="1234567890",
            first_name="John",
            last_name="Smith",
            state="NY",
        )
    )
    db_session.add(
        ExclusionListEntry(
            source="OIG",
            entity_type="individual",
            first_name="Alice",
            last_name="Nguyen",
            state="CA",
        )
    )
    db_session.commit()
    return db_session


def test_screen_exact_match_creates_row_and_events(seeded):
    svc = ExclusionScreeningService(seeded)
    rows = svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(
            entity_type="prescriber",
            entity_id="p1",
            npi="1234567890",
        ),
    )
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].match_confidence == "exact"

    topics = [e.topic for e in events_shim.published_events()]
    assert EVENT_MATCH_FOUND in topics
    assert EVENT_ENTITY_BLOCKED in topics  # exact >= auto_block_threshold
    assert len(NotificationService.all()) == 1


def test_screen_skips_disabled_entity_type(seeded):
    svc = ExclusionScreeningService(seeded)
    cfg = TenantScreeningConfig(entity_types=("pharmacy",))
    rows = svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(entity_type="prescriber", entity_id="p", npi="1234567890"),
        config=cfg,
    )
    assert rows == []


def test_screen_possible_match_no_auto_block(seeded):
    svc = ExclusionScreeningService(seeded)
    cfg = TenantScreeningConfig(auto_block_threshold="exact")
    rows = svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(
            entity_type="prescriber", entity_id="p2", last_name="Nguyen", state="NJ"
        ),
        config=cfg,
    )
    # possible match created, no block event
    assert any(r.match_confidence == "possible" for r in rows)
    assert not any(e.topic == EVENT_ENTITY_BLOCKED for e in events_shim.published_events())


def test_confirm_sets_status_and_emits_block(seeded):
    svc = ExclusionScreeningService(seeded)
    row = svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(entity_type="prescriber", entity_id="p", npi="1234567890"),
    )[0]
    events_shim.reset_events()
    confirmed = svc.confirm(match_id=row.id, user_id="u1")
    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == "u1"
    assert confirmed.reviewed_at is not None
    assert any(e.topic == EVENT_ENTITY_BLOCKED for e in events_shim.published_events())


def test_dismiss_requires_reason_and_persists(seeded):
    svc = ExclusionScreeningService(seeded)
    row = svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(entity_type="prescriber", entity_id="p", npi="1234567890"),
    )[0]
    with pytest.raises(ValueError):
        svc.dismiss(match_id=row.id, user_id="u", reason="   ")

    result = svc.dismiss(match_id=row.id, user_id="u", reason="false positive — different NPI")
    assert result.status == "dismissed"
    assert result.review_reason.startswith("false positive")


def test_load_missing_raises(db_session):
    svc = ExclusionScreeningService(db_session)
    with pytest.raises(LookupError):
        svc.confirm(match_id="nosuch", user_id="u")


def test_status_returns_counts(seeded):
    svc = ExclusionScreeningService(seeded)
    svc.screen_entity(
        tenant_id="t1",
        entity=MatchCandidate(entity_type="prescriber", entity_id="p", npi="1234567890"),
    )
    status = svc.status(tenant_id="t1")
    assert status["match_counts"]["pending"] == 1
    assert status["last_oig_refresh"] is not None
    assert status["last_sam_refresh"] is None


def test_confidence_rank_unknown_returns_zero():
    assert ExclusionScreeningService._confidence_rank("garbage") == 0
