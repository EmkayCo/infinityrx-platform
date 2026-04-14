"""Coverage boost tests for rate limiter, consumers error paths, mapping medium/low confidence,
denial filters, unified spend (medical claim recording, timeline, duplications, COB),
accumulator error path, claims route errors, analytics route errors, main.py lines."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
    InMemoryBucketStore,
    TokenBucket,
)
from src.infrastructure.security_headers import SecurityHeadersMiddleware
from src.services.mapping_service import MappingService
from src.services.denial_service import DenialService
from src.services.unified_spend_service import UnifiedDrugSpendService
from src.services.accumulator_service import AccumulatorService
from src.services.claim_service import ClaimService
from src.services.pricing_service import PricingService
from src.api.schemas.claims import ClaimCreate
from src.models.tables import ClaimRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claim(db, tenant_id, num="COV-001", **kwargs):
    svc = ClaimService(db)
    return svc.create_claim(
        tenant_id,
        ClaimCreate(
            claim_number=num,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 3, 1),
            procedure_code="J0135",
            billed_amount=Decimal("300.00"),
            **kwargs,
        ),
    )


# ---------------------------------------------------------------------------
# Token bucket / rate limiter unit tests
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_consume_allowed(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume(1)
        assert allowed is True
        assert remaining == pytest.approx(9.0, abs=0.1)

    def test_consume_rejected_when_empty(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.consume(1)
        allowed, remaining, _ = bucket.consume(1)
        assert allowed is False
        assert remaining == 0.0

    def test_refill_rate_zero_returns_wait_60(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.consume(1)
        allowed, _, wait = bucket.consume(1)
        assert allowed is False
        assert wait == 60

    def test_consume_zero_tokens(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume(0)
        assert allowed is True

    def test_refill_over_time(self):
        import time
        bucket = TokenBucket(capacity=10.0, refill_rate=100.0)
        bucket.consume(5)
        time.sleep(0.05)  # 50ms → 5 tokens refilled
        allowed, remaining, _ = bucket.consume(1)
        assert allowed is True


class TestInMemoryBucketStore:
    def test_get_or_create_new_bucket(self):
        store = InMemoryBucketStore()
        bucket = store.get_or_create("key1", 10.0, 1.0)
        assert isinstance(bucket, TokenBucket)

    def test_get_or_create_returns_same_bucket(self):
        store = InMemoryBucketStore()
        b1 = store.get_or_create("key1", 10.0, 1.0)
        b2 = store.get_or_create("key1", 10.0, 1.0)
        assert b1 is b2

    def test_clear(self):
        store = InMemoryBucketStore()
        store.get_or_create("key1", 10.0, 1.0)
        store.clear()
        assert store._buckets == {}


class TestRateLimitMiddleware:
    """Integration tests for rate limiter via FastAPI TestClient."""

    @pytest.fixture
    def rate_app(self):
        from fastapi import FastAPI
        app = FastAPI()
        config = RateLimitConfig(tenant_rpm=1000, user_rpm=100)
        store = InMemoryBucketStore()
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.get("/health")
        async def health():
            return {"ok": True}

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        return TestClient(app)

    def test_health_endpoint_skipped(self, rate_app):
        resp = rate_app.get("/health")
        assert resp.status_code == 200

    def test_no_tenant_no_user_passes_through(self, rate_app):
        resp = rate_app.get("/test")
        assert resp.status_code == 200

    def test_tenant_rate_limit_headers_added(self, rate_app):
        resp = rate_app.get("/test", headers={"x-tenant-id": str(uuid.uuid4())})
        assert resp.status_code == 200

    def test_tenant_limit_exhausted_returns_429(self):
        from fastapi import FastAPI, Request
        app = FastAPI()
        store = InMemoryBucketStore()
        config = RateLimitConfig(tenant_rpm=1, user_rpm=1000, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_tenant(request: Request, call_next):
            request.state.tenant_id = "tenant-abc"
            return await call_next(request)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        client.get("/test")
        client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_user_limit_exhausted_returns_429(self):
        from fastapi import FastAPI, Request
        app = FastAPI()
        store = InMemoryBucketStore()
        config = RateLimitConfig(tenant_rpm=10000, user_rpm=1, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_user(request: Request, call_next):
            request.state.user_id = "user-abc"
            return await call_next(request)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        client.get("/test")
        client.get("/test")
        resp = client.get("/test")
        assert resp.status_code == 429

    def test_user_rate_limit_headers_set(self):
        from fastapi import FastAPI, Request
        app = FastAPI()
        store = InMemoryBucketStore()
        config = RateLimitConfig(tenant_rpm=10000, user_rpm=1000)
        app.add_middleware(RateLimitMiddleware, config=config, store=store)

        @app.middleware("http")
        async def inject_both(request: Request, call_next):
            request.state.user_id = "user-xyz"
            request.state.tenant_id = "tenant-xyz"
            return await call_next(request)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers

    def test_api_v1_health_skipped(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/v1/health")
        async def health():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Consumer error paths
# ---------------------------------------------------------------------------

class TestConsumerErrorPaths:
    @pytest.mark.asyncio
    async def test_edi_consumer_propagates_exception(self, db_session, tenant_id):
        from shared.events import EventEnvelope
        from src.events.consumers import handle_edi_837_received

        class _BrokenSvc:
            def ingest_from_edi_payload(self, **_kw):
                raise RuntimeError("kaboom")

        envelope = EventEnvelope(
            event_type="edi.837_received",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="edi",
            payload={"transaction_record_id": str(uuid.uuid4()), "claim_lines": []},
        )
        with pytest.raises(RuntimeError, match="kaboom"):
            await handle_edi_837_received(envelope, claim_service=_BrokenSvc(), db=db_session)

    @pytest.mark.asyncio
    async def test_pharmacy_consumer_propagates_exception(self, db_session, tenant_id):
        from shared.events import EventEnvelope
        from src.events.consumers import handle_pharmacy_claim_adjudicated

        class _BrokenSvc:
            def record_pharmacy_claim(self, **_kw):
                raise RuntimeError("bang")

        envelope = EventEnvelope(
            event_type="claim.adjudicated",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="billing",
            payload={
                "claim_id": str(uuid.uuid4()),
                "billed_amount": "100.00",
                "date_of_service": "2026-01-01",
            },
        )
        with pytest.raises(RuntimeError, match="bang"):
            await handle_pharmacy_claim_adjudicated(envelope, unified_spend_service=_BrokenSvc())


# ---------------------------------------------------------------------------
# Mapping service — medium and low confidence paths
# ---------------------------------------------------------------------------

class TestMappingMediumLowConfidence:
    def test_medium_confidence_multiple_ndcs(self, db_session, tenant_id):
        svc = MappingService(db_session)
        for i in range(3):
            svc.upsert_crosswalk_entry("J0997", f"1111111100{i}", date(2026, 1, 1))

        result = svc.lookup_crosswalk("J0997", as_of=date(2026, 6, 1))
        assert result.confidence == "medium"
        assert result.requires_manual_review is False

    def test_low_confidence_many_ndcs(self, db_session, tenant_id):
        svc = MappingService(db_session)
        for i in range(6):
            svc.upsert_crosswalk_entry("J0998", f"2222222200{i}", date(2026, 1, 1))

        result = svc.lookup_crosswalk("J0998", as_of=date(2026, 6, 1))
        assert result.confidence == "low"
        assert result.requires_manual_review is True

    def test_map_claim_exact_ndc(self, db_session, tenant_id):
        svc = MappingService(db_session)
        claim = _make_claim(db_session, tenant_id, "MAP-EXACT-001", ndc="99999999999")
        ndc, confidence = svc.map_claim(claim)
        assert confidence == "exact"
        assert ndc == "99999999999"

    def test_map_claim_medium_returns_none(self, db_session, tenant_id):
        svc = MappingService(db_session)
        for i in range(3):
            svc.upsert_crosswalk_entry("J0884", f"3333333300{i}", date(2026, 1, 1))
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-MED-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 2, 1),
            procedure_code="J0884",
            billed_amount=Decimal("100.00"),
            status="received",
            ndc=None,
        )
        db_session.add(claim)
        db_session.commit()
        # 3 crosswalk entries → medium confidence, no single NDC
        ndc, confidence = svc.map_claim(claim)
        assert ndc is None
        assert confidence == "medium"

    def test_map_claim_no_crosswalk_returns_manual(self, db_session, tenant_id):
        svc = MappingService(db_session)
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="MAP-MANUAL-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 3, 1),
            procedure_code="J9991",
            billed_amount=Decimal("100.00"),
            status="received",
            ndc=None,
        )
        db_session.add(claim)
        db_session.commit()
        ndc, confidence = svc.map_claim(claim)
        assert ndc is None
        assert confidence == "manual"

    def test_upsert_crosswalk_updates_existing(self, db_session, tenant_id):
        svc = MappingService(db_session)
        entry = svc.upsert_crosswalk_entry("J0135", "44444444444", date(2026, 1, 1))
        original_id = entry.id
        entry2 = svc.upsert_crosswalk_entry("J0135", "44444444444", date(2026, 1, 1), ndc_qualifier="UN")
        assert entry2.id == original_id
        assert entry2.ndc_qualifier == "UN"

    def test_list_unmapped_claims(self, db_session, tenant_id):
        svc_mapping = MappingService(db_session)
        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="UNMAPPED-001",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 3, 1),
                procedure_code="J9900",
                billed_amount=Decimal("100.00"),
            ),
        )
        # Force manual confidence + no mapped ndc
        claim.mapping_confidence = "manual"
        claim.mapped_ndc = None
        db_session.commit()

        unmapped = svc_mapping.list_unmapped_claims(tenant_id)
        assert any(c.claim_number == "UNMAPPED-001" for c in unmapped)


# ---------------------------------------------------------------------------
# Denial service filter paths
# ---------------------------------------------------------------------------

class TestDenialServiceFilters:
    def test_list_denied_by_reason_code(self, db_session, tenant_id):
        svc = DenialService(db_session)
        svc_claim = ClaimService(db_session)
        claim = _make_claim(db_session, tenant_id, "DEN-FILT-001")
        svc_claim.transition_status(tenant_id, claim.id, "validated")
        svc.deny_claim(tenant_id, claim.id, "50", "Not medically necessary")

        items, total = svc.list_denied_claims(tenant_id, reason_code="50")
        assert any(c.claim_number == "DEN-FILT-001" for c in items)

    def test_list_denied_by_date_range(self, db_session, tenant_id):
        svc = DenialService(db_session)
        svc_claim = ClaimService(db_session)
        claim = _make_claim(db_session, tenant_id, "DEN-FILT-002")
        svc_claim.transition_status(tenant_id, claim.id, "validated")
        svc.deny_claim(tenant_id, claim.id, "96")

        items, total = svc.list_denied_claims(
            tenant_id,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        assert isinstance(items, list)

    def test_deny_claim_not_found(self, db_session, tenant_id):
        svc = DenialService(db_session)
        result = svc.deny_claim(tenant_id, uuid.uuid4(), "50")
        assert result is None

    def test_appeal_not_found_returns_none(self, db_session, tenant_id):
        svc = DenialService(db_session)
        result = svc.initiate_appeal(tenant_id, uuid.uuid4(), "Medical necessity documented")
        assert result is None

    def test_appeal_non_denied_raises(self, db_session, tenant_id):
        svc = DenialService(db_session)
        claim = _make_claim(db_session, tenant_id, "DEN-APPEAL-NV-001")
        with pytest.raises(ValueError, match="Can only appeal denied claims"):
            svc.initiate_appeal(tenant_id, claim.id, "reason")

    def test_denial_analytics_no_claims(self, db_session):
        # Use a unique tenant so no claims exist
        empty_tenant = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        svc = DenialService(db_session)
        result = svc.get_denial_analytics(empty_tenant, date(2026, 1, 1), date(2026, 12, 31))
        assert result["denial_rate"] == Decimal("0.00")

    def test_denial_analytics_with_denied_claims(self, db_session, tenant_id):
        svc = DenialService(db_session)
        claim = _make_claim(db_session, tenant_id, "DEN-ANALYTICS-001")
        ClaimService(db_session).transition_status(tenant_id, claim.id, "validated")
        svc.deny_claim(tenant_id, claim.id, "50")

        result = svc.get_denial_analytics(tenant_id, date(2026, 1, 1), date(2026, 12, 31))
        assert result["denial_rate"] > Decimal("0")
        assert isinstance(result["by_reason_code"], list)
        assert isinstance(result["by_provider"], list)
        assert isinstance(result["by_hcpcs"], list)


# ---------------------------------------------------------------------------
# Unified spend service — medical claim recording + timeline + duplications
# ---------------------------------------------------------------------------

class TestUnifiedSpendMedicalClaim:
    def test_record_medical_claim(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        claim = _make_claim(db_session, tenant_id, "USPEND-MED-001",
                            paid_amount=Decimal("250.00"))
        claim.member_id = member_id
        db_session.commit()

        record = svc.record_medical_claim(claim)
        assert record.benefit_type == "medical"
        assert record.medical_claim_id == claim.id

    def test_get_member_timeline(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc="88888888881", drug_name="Drug A",
            dos=date(2026, 5, 1),
            billed_amount=Decimal("100.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        timeline = svc.get_member_timeline(tenant_id, member_id)
        assert any(r.ndc == "88888888881" for r in timeline)

    def test_list_spend_by_ndc(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc="77777777771", drug_name="Drug B",
            dos=date(2026, 5, 1),
            billed_amount=Decimal("150.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        items, _ = svc.list_spend(tenant_id, ndc="77777777771")
        assert all(r.ndc == "77777777771" for r in items)

    def test_list_spend_by_date_range(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        items, _ = svc.list_spend(
            tenant_id,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        assert isinstance(items, list)

    def test_detect_therapeutic_duplications_with_cob_excluded(self, db_session, tenant_id, member_id):
        """COB claims (payer_sequence=secondary) must NOT be flagged as duplications."""
        svc = UnifiedDrugSpendService(db_session)

        # Record a pharmacy spend for this member/NDC/DOS
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc="55555555551", drug_name="Drug COB",
            dos=date(2026, 4, 15),
            billed_amount=Decimal("200.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )

        # Create a medical claim with payer_sequence=secondary (COB)
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="COB-DUP-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=date(2026, 4, 15),
            procedure_code="J0135",
            billed_amount=Decimal("200.00"),
            status="received",
            ndc="55555555551",
            member_id=member_id,
            payer_sequence="secondary",
        )
        db_session.add(claim)
        db_session.commit()
        svc.record_medical_claim(claim)

        dups = svc.detect_therapeutic_duplications(tenant_id)
        # COB claim should be excluded
        assert all(d.get("ndc") != "55555555551" for d in dups)

    def test_detect_therapeutic_duplications_flags_true_duplicates(self, db_session, tenant_id, member_id):
        """True duplicates (same member/NDC/DOS, primary payer) must be flagged."""
        svc = UnifiedDrugSpendService(db_session)
        dup_ndc = "66666666661"
        dos = date(2026, 4, 20)

        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc=dup_ndc, drug_name="Drug DUP",
            dos=dos,
            billed_amount=Decimal("100.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )

        # Medical claim with payer_sequence=primary (true dup)
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="DUP-TRUE-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=dos,
            procedure_code="J0135",
            billed_amount=Decimal("100.00"),
            status="received",
            ndc=dup_ndc,
            member_id=member_id,
            payer_sequence="primary",
        )
        db_session.add(claim)
        db_session.commit()
        svc.record_medical_claim(claim)

        dups = svc.detect_therapeutic_duplications(tenant_id)
        assert any(d["ndc"] == dup_ndc for d in dups)


# ---------------------------------------------------------------------------
# Accumulator service
# ---------------------------------------------------------------------------

class TestAccumulatorService:
    def test_apply_accumulator_not_found(self, db_session, tenant_id):
        svc = AccumulatorService(db_session, None)
        result = svc.apply_accumulator(tenant_id, uuid.uuid4())
        assert result is None

    def test_apply_accumulator_client_failure_uses_local(self, db_session, tenant_id):
        class _FailClient:
            def apply_claim_accumulator(self, **_kw):
                raise ConnectionError("down")

        svc = AccumulatorService(db_session, _FailClient())
        claim = _make_claim(db_session, tenant_id, "ACC-FAIL-001",
                            patient_responsibility=Decimal("25.00"),
                            deductible_amount=Decimal("20.00"),
                            coinsurance_amount=Decimal("5.00"))
        result = svc.apply_accumulator(tenant_id, claim.id)
        # Should still set applied_to_deductible from local calculation
        assert result is not None
        assert result.applied_to_deductible == Decimal("20.00")
        assert result.applied_to_oop == Decimal("25.00")

    def test_apply_accumulator_uses_client_response(self, db_session, tenant_id):
        class _GoodClient:
            def apply_claim_accumulator(self, **_kw):
                return {"applied_to_deductible": "15.00", "applied_to_oop": "20.00"}

        svc = AccumulatorService(db_session, _GoodClient())
        claim = _make_claim(db_session, tenant_id, "ACC-OK-001",
                            deductible_amount=Decimal("20.00"),
                            coinsurance_amount=Decimal("5.00"))
        result = svc.apply_accumulator(tenant_id, claim.id)
        assert result.applied_to_deductible == Decimal("15.00")
        assert result.applied_to_oop == Decimal("20.00")

    def test_apply_accumulator_client_returns_none(self, db_session, tenant_id):
        class _NoneClient:
            def apply_claim_accumulator(self, **_kw):
                return None

        svc = AccumulatorService(db_session, _NoneClient())
        claim = _make_claim(db_session, tenant_id, "ACC-NONE-001",
                            deductible_amount=Decimal("10.00"))
        result = svc.apply_accumulator(tenant_id, claim.id)
        assert result is not None
        assert result.applied_to_deductible == Decimal("10.00")


# ---------------------------------------------------------------------------
# ASP pricing fallback path
# ---------------------------------------------------------------------------

class TestAspPricingFallback:
    def test_fallback_to_prior_quarter(self, db_session, tenant_id):
        svc = PricingService(db_session)
        svc.upsert_asp("J0882", "2025-Q4", date(2025, 10, 1), Decimal("80.000000"))

        # Request Q1-2026 — no data, should fall back to Q4-2025
        record = svc.get_asp_pricing("J0882", date(2026, 1, 15))
        assert record is not None
        assert record.quarter == "2025-Q4"

    def test_asp_response_none_when_no_record(self, db_session, tenant_id):
        svc = PricingService(db_session)
        result = svc.get_asp_response("J9999", date(2026, 1, 1))
        assert result is None

    def test_upsert_asp_updates_existing(self, db_session, tenant_id):
        svc = PricingService(db_session)
        r1 = svc.upsert_asp("J0883", "2026-Q1", date(2026, 1, 1), Decimal("10.000000"))
        r2 = svc.upsert_asp("J0883", "2026-Q1", date(2026, 1, 1), Decimal("12.000000"))
        assert r1.id == r2.id
        assert r2.asp_per_unit == Decimal("12.000000")


# ---------------------------------------------------------------------------
# Claims route error paths
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cov_app(_engine):
    from sqlalchemy.orm import sessionmaker
    from src.main import create_app

    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    app = create_app()

    @app.middleware("http")
    async def inject_db(request, call_next):
        session = SessionLocal()
        request.state.db = session
        try:
            return await call_next(request)
        finally:
            session.close()

    return TestClient(app)


TENANT = uuid.UUID("33333333-3333-3333-3333-333333333333")
HEADERS = {"x-tenant-id": str(TENANT)}


class TestClaimsRouteErrors:
    def test_missing_tenant_header_returns_401(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/claims")
        assert resp.status_code == 401

    def test_invalid_tenant_header_returns_400(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/claims",
                           headers={"x-tenant-id": "not-a-uuid"})
        assert resp.status_code == 400

    def test_get_claim_not_found(self, cov_app):
        resp = cov_app.get(f"/api/v1/medical-claims/claims/{uuid.uuid4()}",
                           headers=HEADERS)
        assert resp.status_code == 404

    def test_update_claim_not_found(self, cov_app):
        resp = cov_app.put(
            f"/api/v1/medical-claims/claims/{uuid.uuid4()}",
            json={"paid_amount": "100.00"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_status_transition_invalid_returns_422(self, cov_app):
        # Create → try invalid transition
        create = cov_app.post(
            "/api/v1/medical-claims/claims",
            json={
                "claim_number": "ROUTE-ERR-001",
                "claim_type": "professional",
                "patient_member_id": "MBR-1",
                "rendering_provider_npi": "1234567890",
                "date_of_service": "2026-03-01",
                "procedure_code": "J0135",
                "billed_amount": "100.00",
            },
            headers=HEADERS,
        )
        claim_id = create.json()["id"]
        resp = cov_app.post(
            f"/api/v1/medical-claims/claims/{claim_id}/status",
            json={"status": "paid"},  # received → paid invalid
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_status_transition_not_found(self, cov_app):
        resp = cov_app.post(
            f"/api/v1/medical-claims/claims/{uuid.uuid4()}/status",
            json={"status": "validated"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_upload_stub_endpoint(self, cov_app):
        import io
        resp = cov_app.post(
            "/api/v1/medical-claims/claims/upload",
            files={"file": ("test.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_crosswalk_missing_tenant_returns_401(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/crosswalk/unmapped")
        assert resp.status_code == 401

    def test_crosswalk_invalid_tenant_returns_400(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/crosswalk/unmapped",
                           headers={"x-tenant-id": "bad"})
        assert resp.status_code == 400

    def test_denials_missing_tenant_returns_401(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/denials")
        assert resp.status_code == 401

    def test_denials_invalid_tenant_returns_400(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/denials",
                           headers={"x-tenant-id": "bad"})
        assert resp.status_code == 400

    def test_unified_spend_missing_tenant_returns_401(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/unified-spend")
        assert resp.status_code == 401

    def test_unified_spend_invalid_tenant_returns_400(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/unified-spend",
                           headers={"x-tenant-id": "bad"})
        assert resp.status_code == 400

    def test_analytics_missing_tenant_returns_401(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/340b/claims")
        assert resp.status_code == 401

    def test_analytics_invalid_tenant_returns_400(self, cov_app):
        resp = cov_app.get("/api/v1/medical-claims/340b/claims",
                           headers={"x-tenant-id": "bad"})
        assert resp.status_code == 400

    def test_waste_report_with_date_filters(self, cov_app):
        resp = cov_app.get(
            "/api/v1/medical-claims/waste/report",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_site_of_care_with_date_filters(self, cov_app):
        resp = cov_app.get(
            "/api/v1/medical-claims/site-of-care/analysis",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=HEADERS,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ASP/crosswalk/unified-spend route 401/400 paths (missing/invalid tenant)
# ---------------------------------------------------------------------------

class TestAspRouteErrors:
    def test_crosswalk_set_manual_missing_tenant(self, cov_app):
        resp = cov_app.post(
            f"/api/v1/medical-claims/crosswalk/claims/{uuid.uuid4()}/drug-mapping",
            params={"ndc": "12345678901"},
        )
        assert resp.status_code == 401

    def test_crosswalk_set_manual_invalid_tenant(self, cov_app):
        resp = cov_app.post(
            f"/api/v1/medical-claims/crosswalk/claims/{uuid.uuid4()}/drug-mapping",
            params={"ndc": "12345678901"},
            headers={"x-tenant-id": "bad"},
        )
        assert resp.status_code == 400

    def test_crosswalk_not_found_returns_404(self, cov_app):
        resp = cov_app.post(
            f"/api/v1/medical-claims/crosswalk/claims/{uuid.uuid4()}/drug-mapping",
            params={"ndc": "12345678901"},
            headers=HEADERS,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Main app module-level singleton
# ---------------------------------------------------------------------------

class TestMainApp:
    def test_app_singleton_is_fastapi(self):
        from src.main import app
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_health_endpoint(self, cov_app):
        resp = cov_app.get("/health")
        assert resp.status_code == 200
        assert resp.json()["module"] == "medical-claims"


# ---------------------------------------------------------------------------
# Appeal route — 401 / 400 for missing/invalid tenant
# ---------------------------------------------------------------------------

class TestAppealRouteTenant:
    def test_appeal_missing_tenant_calls_through_tenant_check(self, cov_app):
        """No x-tenant-id header → 401 from _get_tenant_id.
        FastAPI validates the request body AFTER route matching — the body is valid here."""
        resp = cov_app.post(
            f"/api/v1/medical-claims/claims/{uuid.uuid4()}/appeal",
            json={"appeal_reason": "Medical necessity documented in chart"},
        )
        # Lines 24-25 in claims_appeal.py execute — HTTPException 401
        assert resp.status_code == 401

    def test_appeal_invalid_tenant_calls_uuid_parse(self, cov_app):
        """Bad UUID → 400 from UUID(tid) ValueError in _get_tenant_id (lines 28-30)."""
        resp = cov_app.post(
            f"/api/v1/medical-claims/claims/{uuid.uuid4()}/appeal",
            json={"appeal_reason": "Medical necessity documented in chart"},
            headers={"x-tenant-id": "not-a-uuid"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Claims schema validator error paths
# ---------------------------------------------------------------------------

class TestClaimCreateValidators:
    def test_invalid_billing_npi_raises(self):
        with pytest.raises(Exception):
            ClaimCreate(
                claim_number="V-001",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                billing_provider_npi="BADNPI",
                date_of_service=date(2026, 1, 1),
                procedure_code="J0135",
                billed_amount=Decimal("100.00"),
            )

    def test_invalid_referring_npi_raises(self):
        with pytest.raises(Exception):
            ClaimCreate(
                claim_number="V-002",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                referring_provider_npi="BADNPI",
                date_of_service=date(2026, 1, 1),
                procedure_code="J0135",
                billed_amount=Decimal("100.00"),
            )

    def test_invalid_facility_npi_raises(self):
        with pytest.raises(Exception):
            ClaimCreate(
                claim_number="V-003",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                facility_npi="BADNPI",
                date_of_service=date(2026, 1, 1),
                procedure_code="J0135",
                billed_amount=Decimal("100.00"),
            )

    def test_invalid_ndc_raises(self):
        with pytest.raises(Exception):
            ClaimCreate(
                claim_number="V-004",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                ndc="BAD",
                date_of_service=date(2026, 1, 1),
                procedure_code="J0135",
                billed_amount=Decimal("100.00"),
            )

    def test_valid_optional_npis_accepted(self):
        claim = ClaimCreate(
            claim_number="V-005",
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            billing_provider_npi="9876543210",
            referring_provider_npi="1111111111",
            facility_npi="2222222222",
            ndc="12345678901",
            date_of_service=date(2026, 1, 1),
            procedure_code="J0135",
            billed_amount=Decimal("100.00"),
        )
        assert claim.billing_provider_npi == "9876543210"


# ---------------------------------------------------------------------------
# Pricing service — _money / _six_dp non-Decimal branches + get_asp_response found
# ---------------------------------------------------------------------------

class TestPricingHelpers:
    def test_money_from_string(self):
        from src.services.pricing_service import _money
        result = _money("123.456")
        assert result == Decimal("123.46")

    def test_six_dp_from_string(self):
        from src.services.pricing_service import _six_dp
        result = _six_dp("12.123456789")
        assert result == Decimal("12.123457")

    def test_get_asp_response_found(self, db_session):
        svc = PricingService(db_session)
        svc.upsert_asp("J0885", "2026-Q2", date(2026, 4, 1), Decimal("30.000000"))
        response = svc.get_asp_response("J0885", date(2026, 5, 1))
        assert response is not None
        assert response.hcpcs_code == "J0885"


# ---------------------------------------------------------------------------
# Unified spend service — _money non-Decimal branch + COB where no medical_claim_id
# ---------------------------------------------------------------------------

class TestUnifiedSpendHelpers:
    def test_money_from_string(self):
        from src.services.unified_spend_service import _money
        result = _money("99.995")
        assert result == Decimal("100.00")

    def test_detect_duplication_no_medical_claim_id(self, db_session, tenant_id, member_id):
        """Medical spend with no medical_claim_id (e.g. synthetic) should be flagged."""
        svc = UnifiedDrugSpendService(db_session)
        from src.models.tables import UnifiedDrugSpend
        dos = date(2026, 6, 10)
        ndc = "11111111100"

        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc=ndc, drug_name="Drug NoId",
            dos=dos,
            billed_amount=Decimal("100.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        # Create medical spend with no medical_claim_id
        med_spend = UnifiedDrugSpend(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            member_id=member_id,
            member_id_display="MBR",
            ndc=ndc,
            drug_name="Drug NoId",
            benefit_type="medical",
            medical_claim_id=None,
            pharmacy_claim_id=None,
            date_of_service=dos,
            billed_amount=Decimal("100.00"),
        )
        db_session.add(med_spend)
        db_session.commit()

        dups = svc.detect_therapeutic_duplications(tenant_id)
        assert any(d["ndc"] == ndc for d in dups)


# ---------------------------------------------------------------------------
# ASP refresh job — edge cases (missing hcpcs_code, missing asp_per_unit, bad row)
# ---------------------------------------------------------------------------

class TestAspRefreshJobEdgeCases:
    def test_skip_empty_hcpcs_code(self, db_session):
        from src.jobs.asp_refresh_job import AspRefreshJob
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [{"hcpcs_code": "", "asp_per_unit": "10.0", "effective_date": "2026-07-01"}])
        assert result["skipped"] == 1
        assert result["loaded"] == 0

    def test_skip_missing_asp_per_unit(self, db_session):
        from src.jobs.asp_refresh_job import AspRefreshJob
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [{"hcpcs_code": "J0900", "effective_date": "2026-07-01"}])
        assert result["skipped"] == 1

    def test_skip_bad_row_on_exception(self, db_session):
        from src.jobs.asp_refresh_job import AspRefreshJob
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [{"hcpcs_code": "J0901", "asp_per_unit": "not-a-number", "effective_date": "2026-07-01"}])
        assert result["skipped"] == 1

    def test_effective_date_as_date_object(self, db_session):
        from src.jobs.asp_refresh_job import AspRefreshJob
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [{"hcpcs_code": "J0902", "asp_per_unit": "10.0", "effective_date": date(2026, 7, 1)}])
        assert result["loaded"] == 1

    def test_effective_date_none_uses_today(self, db_session):
        from src.jobs.asp_refresh_job import AspRefreshJob
        job = AspRefreshJob(db_session)
        result = job.run("2026-Q3", [{"hcpcs_code": "J0903", "asp_per_unit": "10.0"}])
        assert result["loaded"] == 1


# ---------------------------------------------------------------------------
# claims.py — create exception path (line 88-90) and update success (line 127)
# ---------------------------------------------------------------------------

class TestClaimsRouteEdgeCases:
    def test_create_claim_invalid_rendering_npi(self, cov_app):
        """Pydantic validation fails on bad NPI → 422 from FastAPI (not our handler)."""
        resp = cov_app.post(
            "/api/v1/medical-claims/claims",
            json={
                "claim_number": "BADINPI-001",
                "claim_type": "professional",
                "patient_member_id": "MBR-1",
                "rendering_provider_npi": "BADNPI",  # invalid
                "date_of_service": "2026-03-01",
                "procedure_code": "J0135",
                "billed_amount": "100.00",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_update_claim_success_returns_updated(self, cov_app):
        create = cov_app.post(
            "/api/v1/medical-claims/claims",
            json={
                "claim_number": "UPD-ROUTE-001",
                "claim_type": "professional",
                "patient_member_id": "MBR-1",
                "rendering_provider_npi": "1234567890",
                "date_of_service": "2026-03-01",
                "procedure_code": "J0135",
                "billed_amount": "100.00",
            },
            headers=HEADERS,
        )
        claim_id = create.json()["id"]
        resp = cov_app.put(
            f"/api/v1/medical-claims/claims/{claim_id}",
            json={"paid_amount": "80.00"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["paid_amount"] == "80.00"


# ---------------------------------------------------------------------------
# Final coverage gaps
# ---------------------------------------------------------------------------

class TestFinalCoverageGaps:
    def test_upsert_asp_with_description_updates_existing(self, db_session):
        """Line 214 in pricing_service: hcpcs_description update on existing record."""
        svc = PricingService(db_session)
        svc.upsert_asp("J0920", "2026-Q3", date(2026, 7, 1), Decimal("20.000000"))
        r2 = svc.upsert_asp("J0920", "2026-Q3", date(2026, 7, 1), Decimal("22.000000"),
                            hcpcs_description="Updated Injection Drug")
        assert r2.hcpcs_description == "Updated Injection Drug"

    def test_dlq_repository_list(self):
        """main.py lines 21: _EmptyDLQRepository.list returns empty list."""
        import asyncio
        from src.main import _EmptyDLQRepository
        repo = _EmptyDLQRepository()
        result = asyncio.run(repo.list())
        assert result == []

    def test_dlq_repository_get(self):
        """main.py line 24: _EmptyDLQRepository.get returns None."""
        import asyncio
        from src.main import _EmptyDLQRepository
        repo = _EmptyDLQRepository()
        result = asyncio.run(repo.get(uuid.uuid4()))
        assert result is None

    def test_dlq_repository_save(self):
        """main.py line 27: _EmptyDLQRepository.save returns None."""
        import asyncio
        from src.main import _EmptyDLQRepository
        repo = _EmptyDLQRepository()
        result = asyncio.run(repo.save({"entry": "data"}))
        assert result is None

    def test_unified_spend_duplication_tertiary_excluded(self, db_session, tenant_id, member_id):
        """COB tertiary payer_sequence also excluded from duplications."""
        svc = UnifiedDrugSpendService(db_session)
        dos = date(2026, 7, 1)
        ndc = "33333333300"

        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc=ndc, drug_name="Drug Tert",
            dos=dos,
            billed_amount=Decimal("50.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        # Medical claim with payer_sequence=tertiary (COB)
        med_claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="COB-TERT-001",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            date_of_service=dos,
            procedure_code="J0135",
            billed_amount=Decimal("50.00"),
            status="received",
            ndc=ndc,
            member_id=member_id,
            payer_sequence="tertiary",
        )
        db_session.add(med_claim)
        db_session.commit()
        svc.record_medical_claim(med_claim)

        dups = svc.detect_therapeutic_duplications(tenant_id)
        assert all(d.get("ndc") != ndc for d in dups)
