from __future__ import annotations

import pytest

from src.models import ExclusionListEntry


@pytest.fixture
def seeded_list(db_session):
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
    db_session.commit()


def test_screen_creates_match_and_listable(client, tenant_admin_a, seeded_list):
    resp = client.post(
        "/api/v1/exclusions/screen",
        json={
            "entity_type": "prescriber",
            "entity_id": "p1",
            "npi": "1234567890",
        },
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) == 1
    assert matches[0]["match_confidence"] == "exact"

    lst = client.get("/api/v1/exclusions/matches").json()
    assert len(lst) == 1

    filtered = client.get("/api/v1/exclusions/matches?status=pending&confidence=exact").json()
    assert len(filtered) == 1


def test_review_confirm(client, tenant_admin_a, seeded_list):
    match = client.post(
        "/api/v1/exclusions/screen",
        json={"entity_type": "prescriber", "entity_id": "p1", "npi": "1234567890"},
    ).json()[0]
    resp = client.put(
        f"/api/v1/exclusions/matches/{match['id']}", json={"action": "confirm"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_review_dismiss_requires_reason(client, tenant_admin_a, seeded_list):
    match = client.post(
        "/api/v1/exclusions/screen",
        json={"entity_type": "prescriber", "entity_id": "p1", "npi": "1234567890"},
    ).json()[0]

    bad = client.put(
        f"/api/v1/exclusions/matches/{match['id']}", json={"action": "dismiss"}
    )
    assert bad.status_code == 422

    ok = client.put(
        f"/api/v1/exclusions/matches/{match['id']}",
        json={"action": "dismiss", "reason": "different person"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "dismissed"


def test_review_dismiss_blank_reason_rejected(client, tenant_admin_a, seeded_list):
    match = client.post(
        "/api/v1/exclusions/screen",
        json={"entity_type": "prescriber", "entity_id": "p1", "npi": "1234567890"},
    ).json()[0]
    resp = client.put(
        f"/api/v1/exclusions/matches/{match['id']}",
        json={"action": "dismiss", "reason": "   "},
    )
    # Empty reason is caught at the endpoint level (missing) OR via the service-level
    # ValueError → 422. Either way, not a success.
    assert resp.status_code == 422


def test_review_match_not_found(client, tenant_admin_a):
    resp = client.put("/api/v1/exclusions/matches/nosuch", json={"action": "confirm"})
    assert resp.status_code == 404


def test_exclusion_status_endpoint(client, tenant_admin_a, seeded_list):
    client.post(
        "/api/v1/exclusions/screen",
        json={"entity_type": "prescriber", "entity_id": "p", "npi": "1234567890"},
    )
    resp = client.get("/api/v1/exclusions/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_counts"]["pending"] >= 1


def test_tenant_isolation_exclusion_matches(client, tenant_admin_a, seeded_list):
    match = client.post(
        "/api/v1/exclusions/screen",
        json={"entity_type": "prescriber", "entity_id": "p1", "npi": "1234567890"},
    ).json()[0]

    # switch to a different tenant admin
    from src._shim import auth as auth_shim
    import uuid as _uuid

    auth_shim.set_current_user(
        auth_shim.CurrentUser(
            id=_uuid.uuid4(),
            tenant_id=_uuid.UUID("22222222-2222-2222-2222-222222222222"),
            email="b@example.com",
            status="active",
            roles=("tenant_admin",),
        )
    )
    lst = client.get("/api/v1/exclusions/matches").json()
    assert lst == []
    # Direct review 404s
    assert (
        client.put(f"/api/v1/exclusions/matches/{match['id']}", json={"action": "confirm"}).status_code
        == 404
    )
    status = client.get("/api/v1/exclusions/status").json()
    assert status["match_counts"]["pending"] == 0
