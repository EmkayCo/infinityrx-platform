"""Unit tests for claims ingestion service — 100% coverage on financial paths."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.services.claims import ClaimIngestRequest, ClaimsService
from src.services.routing import ClassifiedClaim
from src.utils.constants import (
    CLAIM_STATUS_CLASSIFIED,
    CLAIM_STATUS_INGESTED,
    ROUTE_ECHO,
    ROUTE_EXCLUDED,
    ROUTE_STATEMENT,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
USER = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _req(
    auth_number: str = "AUTH001",
    net_amount: Decimal = Decimal("100.00"),
    claim_type: str = "new",
    is_reversal: bool = False,
) -> ClaimIngestRequest:
    return ClaimIngestRequest(
        tenant_id=TENANT,
        source_type="api",
        auth_number=auth_number,
        claim_type=claim_type,
        pharmacy_npi="1234567890",
        date_of_service=date(2026, 1, 15),
        net_amount=net_amount,
        client_id=CLIENT,
        program_id=PROGRAM,
        reversal_of_auth="ORIG001" if is_reversal else None,
    )


def _make_service(db=None, events=None) -> ClaimsService:
    db = db or MagicMock()
    events = events or MagicMock()
    return ClaimsService(db=db, events=events)


class TestClaimIngestRequest:
    def test_net_amount_stored_as_decimal(self) -> None:
        req = _req(net_amount=Decimal("99.99"))
        assert isinstance(req.net_amount, Decimal)

    def test_validates_pharmacy_npi_length(self) -> None:
        with pytest.raises(Exception):
            ClaimIngestRequest(
                tenant_id=TENANT,
                source_type="api",
                auth_number="A001",
                claim_type="new",
                pharmacy_npi="123",  # too short
                date_of_service=date(2026, 1, 15),
                net_amount=Decimal("100.00"),
                client_id=CLIENT,
                program_id=PROGRAM,
            )


class TestClaimsServiceIngestion:
    def test_ingest_returns_claim_with_ingested_status(self) -> None:
        svc = _make_service()
        req = _req()
        claim = svc.ingest(req)
        assert claim.status == CLAIM_STATUS_INGESTED

    def test_ingest_stores_net_amount_as_decimal(self) -> None:
        svc = _make_service()
        req = _req(net_amount=Decimal("250.75"))
        claim = svc.ingest(req)
        assert claim.net_amount == money("250.75")
        assert isinstance(claim.net_amount, Decimal)

    def test_ingest_publishes_claim_ingested_event(self) -> None:
        events = MagicMock()
        svc = _make_service(events=events)
        claim = svc.ingest(_req())
        events.publish.assert_called_once()
        args = events.publish.call_args
        assert "claim.ingested" in str(args)

    def test_ingest_sets_tenant_id(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        assert claim.tenant_id == TENANT

    def test_ingest_sets_date_received(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        assert claim.date_received is not None

    def test_ingest_zero_amount_allowed(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req(net_amount=Decimal("0.00")))
        assert claim.net_amount == Decimal("0.00")

    def test_reversal_claim_links_to_original(self) -> None:
        svc = _make_service()
        req = _req(is_reversal=True)
        claim = svc.ingest(req)
        assert claim.reversal_of_auth == "ORIG001"

    def test_ingest_assigns_uuid(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        assert claim.id is not None
        assert isinstance(claim.id, uuid.UUID)


class TestClaimsServiceClassification:
    def _classified(
        self,
        route: str = ROUTE_ECHO,
        vendor_id: uuid.UUID | None = None,
        schedule: str | None = "daily",
        is_excluded: bool = False,
        is_statement: bool = False,
    ) -> ClassifiedClaim:
        return ClassifiedClaim(
            claim_id=uuid.uuid4(),
            classified=True,
            payment_route=route,
            payment_vendor_config_id=vendor_id,
            payment_schedule=schedule,
            matched_rule_id=uuid.uuid4(),
            is_excluded=is_excluded,
            is_statement=is_statement,
        )

    def test_apply_classification_updates_route(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        result = self._classified(route=ROUTE_ECHO)
        svc.apply_classification(claim, result)
        assert claim.payment_route == ROUTE_ECHO
        assert claim.status == CLAIM_STATUS_CLASSIFIED

    def test_apply_excluded_classification(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        result = self._classified(route=ROUTE_EXCLUDED, is_excluded=True)
        svc.apply_classification(claim, result)
        assert claim.is_excluded is True
        assert claim.status == CLAIM_STATUS_CLASSIFIED

    def test_apply_statement_classification(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        result = self._classified(route=ROUTE_STATEMENT, is_statement=True)
        svc.apply_classification(claim, result)
        assert claim.is_statement is True

    def test_apply_classification_publishes_classified_event(self) -> None:
        events = MagicMock()
        svc = _make_service(events=events)
        claim = svc.ingest(_req())
        events.reset_mock()
        result = self._classified(route=ROUTE_ECHO)
        svc.apply_classification(claim, result)
        events.publish.assert_called_once()
        args = events.publish.call_args
        assert "claim.classified" in str(args)

    def test_unclassified_leaves_claim_in_ingested_status(self) -> None:
        svc = _make_service()
        claim = svc.ingest(_req())
        unclassified = ClassifiedClaim(
            claim_id=claim.id,
            classified=False,
            payment_route=None,
            payment_vendor_config_id=None,
            payment_schedule=None,
            matched_rule_id=None,
        )
        svc.apply_classification(claim, unclassified)
        assert claim.status == CLAIM_STATUS_INGESTED


class TestDuplicateDetection:
    def test_duplicate_auth_number_raises_error(self) -> None:
        svc = _make_service()
        existing_auths = {"AUTH001"}
        with pytest.raises(ValueError, match="duplicate"):
            svc.check_duplicate("AUTH001", existing_auths, reversal_of=None)

    def test_reversal_of_existing_auth_allowed(self) -> None:
        svc = _make_service()
        existing_auths = {"ORIG001"}
        # Reversal references ORIG001 and has its own unique auth number
        svc.check_duplicate("REV001", existing_auths, reversal_of="ORIG001")

    def test_new_unique_auth_allowed(self) -> None:
        svc = _make_service()
        existing_auths = {"AUTH001"}
        svc.check_duplicate("AUTH002", existing_auths, reversal_of=None)
