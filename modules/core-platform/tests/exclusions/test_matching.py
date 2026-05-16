from __future__ import annotations

import pytest

from src.exclusions.matching import (
    ExactMatcher,
    ExclusionMatcher,
    FuzzyMatcher,
    MatchCandidate,
)
from src.models import ExclusionListEntry


@pytest.fixture
def seeded(db_session):
    db_session.add_all(
        [
            ExclusionListEntry(
                source="OIG",
                entity_type="individual",
                npi="1234567890",
                first_name="John",
                last_name="Smith",
                state="NY",
            ),
            ExclusionListEntry(
                source="OIG",
                entity_type="individual",
                first_name="Johnathan",
                last_name="Smythe",
                state="NY",
            ),
            ExclusionListEntry(
                source="SAM",
                entity_type="organization",
                organization_name="Acme Health LLC",
                state="TX",
            ),
            ExclusionListEntry(
                source="OIG",
                entity_type="individual",
                first_name="Alice",
                last_name="Nguyen",
                state="CA",
            ),
        ]
    )
    db_session.commit()
    return db_session


def test_exact_match_by_npi(seeded):
    res = ExactMatcher().match(
        seeded,
        MatchCandidate(entity_type="prescriber", entity_id="p1", npi="1234567890"),
    )
    assert len(res) == 1
    assert res[0].confidence == "exact"


def test_exact_no_npi_returns_empty(seeded):
    res = ExactMatcher().match(seeded, MatchCandidate(entity_type="prescriber", entity_id="p1"))
    assert res == []


def test_fuzzy_probable_name_and_state(seeded):
    res = FuzzyMatcher(probable_threshold=85, possible_threshold=70).match(
        seeded,
        MatchCandidate(
            entity_type="prescriber",
            entity_id="p1",
            first_name="Jonathan",
            last_name="Smythe",
            state="NY",
        ),
    )
    assert any(r.confidence == "probable" for r in res)


def test_fuzzy_possible_last_name_only(seeded):
    res = FuzzyMatcher().match(
        seeded,
        MatchCandidate(entity_type="prescriber", entity_id="p1", last_name="Nguyen", state="NJ"),
    )
    assert any(r.confidence == "possible" for r in res)


def test_fuzzy_no_last_name_returns_empty(seeded):
    res = FuzzyMatcher().match(
        seeded, MatchCandidate(entity_type="prescriber", entity_id="p1")
    )
    assert res == []


def test_fuzzy_organization_probable(seeded):
    res = FuzzyMatcher(probable_threshold=80, possible_threshold=60).match(
        seeded,
        MatchCandidate(
            entity_type="pharmacy", entity_id="ph1", organization_name="ACME Health LLC"
        ),
    )
    assert any(r.confidence == "probable" for r in res)


def test_fuzzy_organization_possible(seeded):
    res = FuzzyMatcher(probable_threshold=99, possible_threshold=70).match(
        seeded,
        MatchCandidate(
            entity_type="pharmacy",
            entity_id="ph1",
            organization_name="Acme Healthcare",
        ),
    )
    assert any(r.confidence == "possible" for r in res)


def test_exclusion_matcher_combines_and_dedupes(seeded):
    # Candidate matches both by NPI (exact) and fuzzy name — ensure dedupe keeps exact
    m = ExclusionMatcher()
    res = m.screen(
        seeded,
        MatchCandidate(
            entity_type="prescriber",
            entity_id="p",
            npi="1234567890",
            first_name="John",
            last_name="Smith",
            state="NY",
        ),
    )
    by_id = {r.exclusion_list_id: r for r in res}
    # The row with NPI appears only once, as 'exact'
    for r in res:
        assert r.confidence in {"exact", "probable", "possible"}
    exact_hits = [r for r in res if r.confidence == "exact"]
    assert len(exact_hits) == 1


def test_source_filter(seeded):
    m = ExclusionMatcher()
    res = m.screen(
        seeded,
        MatchCandidate(entity_type="pharmacy", entity_id="p", organization_name="Acme Health LLC"),
        sources=("OIG",),
    )
    assert all(r.source == "OIG" for r in res)  # none match → empty list is also valid


# ---------------------------------------------------------------------------
# BLOCK-3 reinstate_date filter tests (P0a v2)
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_with_reinstated(db_session):
    """Fixture with both active and reinstated exclusion rows.

    The reinstated rows have reinstate_date set to a past timestamp.
    ExactMatcher and FuzzyMatcher MUST return zero matches for these rows
    even when NPI or name matches perfectly.
    """
    from datetime import datetime, timezone
    reinstated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    db_session.add_all(
        [
            # Active row — should match
            ExclusionListEntry(
                source="OIG",
                entity_type="individual",
                npi="1234567890",
                first_name="John",
                last_name="Smith",
                state="NY",
                reinstate_date=None,
            ),
            # Reinstated row with same NPI — MUST NOT match
            ExclusionListEntry(
                source="OIG",
                entity_type="individual",
                npi="9876543210",
                first_name="Jane",
                last_name="Doe",
                state="CA",
                reinstate_date=reinstated_at,
            ),
            # Reinstated organization row — MUST NOT match by fuzzy name
            ExclusionListEntry(
                source="SAM",
                entity_type="organization",
                organization_name="Reinstated Health Corp",
                state="TX",
                reinstate_date=reinstated_at,
            ),
        ]
    )
    db_session.commit()
    return db_session


def test_exact_matcher_excludes_reinstated_npi(seeded_with_reinstated):
    """ExactMatcher returns 0 results when the matching NPI is reinstated."""
    res = ExactMatcher().match(
        seeded_with_reinstated,
        MatchCandidate(entity_type="prescriber", entity_id="p1", npi="9876543210"),
    )
    assert res == [], "reinstated NPI must not produce an exact match"


def test_exact_matcher_returns_active_npi(seeded_with_reinstated):
    """ExactMatcher still returns active rows normally."""
    res = ExactMatcher().match(
        seeded_with_reinstated,
        MatchCandidate(entity_type="prescriber", entity_id="p1", npi="1234567890"),
    )
    assert len(res) == 1
    assert res[0].confidence == "exact"


def test_fuzzy_matcher_excludes_reinstated_org(seeded_with_reinstated):
    """FuzzyMatcher returns 0 results for an org name whose row is reinstated."""
    res = FuzzyMatcher(probable_threshold=85, possible_threshold=70).match(
        seeded_with_reinstated,
        MatchCandidate(
            entity_type="pharmacy",
            entity_id="ph1",
            organization_name="Reinstated Health Corp",
        ),
    )
    assert res == [], "reinstated organization must not produce a fuzzy match"


def test_fuzzy_matcher_excludes_reinstated_individual(seeded_with_reinstated):
    """FuzzyMatcher returns 0 results for a name whose row is reinstated."""
    res = FuzzyMatcher(probable_threshold=85, possible_threshold=70).match(
        seeded_with_reinstated,
        MatchCandidate(
            entity_type="prescriber",
            entity_id="p1",
            first_name="Jane",
            last_name="Doe",
            state="CA",
        ),
    )
    assert res == [], "reinstated individual must not produce a fuzzy match"
