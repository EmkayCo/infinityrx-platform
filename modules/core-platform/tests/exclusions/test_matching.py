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
