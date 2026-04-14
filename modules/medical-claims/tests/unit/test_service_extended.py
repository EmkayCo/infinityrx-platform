"""Additional unit tests for uncovered service paths."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal


from src.services.claim_service import ClaimService, _parse_date
from src.services.pricing_service import PricingService
from src.services.mapping_service import MappingService
from src.services.unified_spend_service import UnifiedDrugSpendService
from src.services.detection_340b_service import Detection340bService
from src.clients.drug_database_client import DrugDatabaseClient
from src.api.schemas.claims import ClaimCreate, ClaimUpdate
from src.models.tables import ClaimRecord


def _make_claim(db, tenant_id, num="SVC-001", **kwargs):
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


class TestClaimUpdate:
    def test_update_claim_fields(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = _make_claim(db_session, tenant_id, "UPD-001")
        updated = svc.update_claim(
            tenant_id, claim.id,
            ClaimUpdate(allowed_amount=Decimal("250.00"), paid_amount=Decimal("250.00")),
        )
        assert updated.allowed_amount == Decimal("250.00")

    def test_update_claim_not_found(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        result = svc.update_claim(tenant_id, uuid.uuid4(), ClaimUpdate(paid_amount=Decimal("100.00")))
        assert result is None

    def test_update_money_rounded(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        claim = _make_claim(db_session, tenant_id, "UPD-002")
        updated = svc.update_claim(
            tenant_id, claim.id,
            ClaimUpdate(paid_amount=Decimal("100.555")),
        )
        assert updated.paid_amount == Decimal("100.56")


class TestClaimListFilters:
    def test_list_by_procedure_code(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        _make_claim(db_session, tenant_id, "FILT-001")
        items, _ = svc.list_claims(tenant_id, procedure_code="J0135")
        assert len(items) >= 1

    def test_list_by_ndc(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        _make_claim(db_session, tenant_id, "FILT-002", ndc="11111111111")
        items, _ = svc.list_claims(tenant_id, ndc="11111111111")
        assert any(c.ndc == "11111111111" for c in items)

    def test_list_by_patient_member_id(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        svc.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="FILT-003",
                claim_type="professional",
                patient_member_id="SPECIFIC-MBR",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 3, 1),
                procedure_code="J0135",
                billed_amount=Decimal("300.00"),
            ),
        )
        items, _ = svc.list_claims(tenant_id, patient_member_id="SPECIFIC-MBR")
        assert all(c.patient_member_id == "SPECIFIC-MBR" for c in items)

    def test_list_by_date_range(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        items, _ = svc.list_claims(
            tenant_id,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        assert isinstance(items, list)

    def test_list_by_rendering_provider_npi(self, db_session, tenant_id):
        svc = ClaimService(db_session)
        items, _ = svc.list_claims(tenant_id, rendering_provider_npi="1234567890")
        assert isinstance(items, list)


class TestPricingServiceClaim:
    def test_price_claim_saves_allowed_and_paid(self, db_session, tenant_id):
        svc_pricing = PricingService(db_session)
        svc_pricing.upsert_asp("J0135", "2026-Q1", date(2026, 1, 1), Decimal("100.000000"))

        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="PRICE-001",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 2, 1),
                procedure_code="J0135",
                billed_amount=Decimal("200.00"),
                drug_quantity=Decimal("2.000"),
            ),
        )
        updated = svc_pricing.price_claim(tenant_id, claim.id)
        assert updated.allowed_amount is not None
        assert updated.paid_amount is not None
        assert updated.status == "priced"

    def test_price_claim_no_asp_data(self, db_session, tenant_id):
        svc_pricing = PricingService(db_session)
        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="PRICE-002",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 3, 1),
                procedure_code="J9997",  # no ASP data
                billed_amount=Decimal("200.00"),
            ),
        )
        updated = svc_pricing.price_claim(tenant_id, claim.id)
        # Should return claim without pricing applied
        assert updated is not None
        assert updated.allowed_amount is None

    def test_price_claim_pays_lesser_of_billed_allowed(self, db_session, tenant_id):
        svc_pricing = PricingService(db_session)
        svc_pricing.upsert_asp("J0881", "2026-Q1", date(2026, 1, 1), Decimal("50.000000"))

        svc_claim = ClaimService(db_session)
        # Billed 1000.00 but ASP + 6% * 1 qty = 53.00
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="PRICE-003",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 2, 1),
                procedure_code="J0881",
                billed_amount=Decimal("1000.00"),
                drug_quantity=Decimal("1.000"),
            ),
        )
        updated = svc_pricing.price_claim(tenant_id, claim.id)
        assert updated.paid_amount <= updated.billed_amount
        assert updated.paid_amount == updated.allowed_amount

    def test_price_claim_not_found(self, db_session, tenant_id):
        svc = PricingService(db_session)
        result = svc.price_claim(tenant_id, uuid.uuid4())
        assert result is None

    def test_apply_waste_not_found(self, db_session, tenant_id):
        svc = PricingService(db_session)
        result = svc.apply_waste(tenant_id, uuid.uuid4(), Decimal("1.000"))
        assert result is None

    def test_apply_waste_persists(self, db_session, tenant_id):
        svc_pricing = PricingService(db_session)
        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="WASTE-SVC-001",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 2, 1),
                procedure_code="J0135",
                billed_amount=Decimal("200.00"),
                drug_quantity=Decimal("2.000"),
                drug_unit_price=Decimal("100.000000"),
            ),
        )
        updated = svc_pricing.apply_waste(tenant_id, claim.id, Decimal("1.500"))
        assert updated.waste_quantity == Decimal("0.500")
        assert updated.waste_amount == Decimal("50.00")

    def test_apply_waste_no_quantity_is_noop(self, db_session, tenant_id):
        svc_pricing = PricingService(db_session)
        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="WASTE-SVC-002",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 2, 1),
                procedure_code="J0135",
                billed_amount=Decimal("200.00"),
                # No drug_quantity or drug_unit_price
            ),
        )
        updated = svc_pricing.apply_waste(tenant_id, claim.id, Decimal("1.000"))
        assert updated.waste_quantity is None


class TestMappingApplyToClaim:
    def test_apply_mapping_persists(self, db_session, tenant_id):
        svc_mapping = MappingService(db_session)
        svc_mapping.upsert_crosswalk_entry("J0135", "55555555555", date(2026, 1, 1))

        svc_claim = ClaimService(db_session)
        claim = svc_claim.create_claim(
            tenant_id,
            ClaimCreate(
                claim_number="MAP-APPLY-001",
                claim_type="professional",
                patient_member_id="MBR-1",
                rendering_provider_npi="1234567890",
                date_of_service=date(2026, 2, 1),
                procedure_code="J0135",
                billed_amount=Decimal("300.00"),
                ndc=None,
            ),
        )
        updated = svc_mapping.apply_mapping_to_claim(tenant_id, claim.id)
        assert updated.mapped_ndc == "55555555555"
        assert updated.mapping_confidence == "high"

    def test_apply_mapping_not_found(self, db_session, tenant_id):
        svc = MappingService(db_session)
        result = svc.apply_mapping_to_claim(tenant_id, uuid.uuid4())
        assert result is None


class TestDrugDatabaseClient:
    def test_validate_valid_ndc(self):
        client = DrugDatabaseClient()
        assert client.validate_ndc("12345678901") is True

    def test_validate_invalid_ndc(self):
        client = DrugDatabaseClient()
        assert client.validate_ndc("BADNDC") is False

    def test_get_drug_info_returns_none(self):
        client = DrugDatabaseClient()
        assert client.get_drug_info("12345678901") is None


class TestParseDateHelper:
    def test_parse_date_from_str(self):
        result = _parse_date("2026-03-15")
        from datetime import date
        assert result == date(2026, 3, 15)

    def test_parse_date_from_date_obj(self):
        from datetime import date
        d = date(2026, 3, 15)
        assert _parse_date(d) == d

    def test_parse_date_from_none(self):
        from datetime import date
        result = _parse_date(None)
        assert isinstance(result, date)


class TestDetection340bLookupFailure:
    def test_lookup_failure_defaults_to_false(self, db_session, tenant_id):
        """If the pharmacy directory client raises, return False (conservative)."""
        class _FailingClient:
            def is_340b_entity(self, npi, tenant_id):
                raise ConnectionError("Service unavailable")

        svc = Detection340bService(db_session, _FailingClient())
        claim = ClaimRecord(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            claim_number="340B-FAIL",
            claim_line_number=1,
            claim_type="professional",
            patient_member_id="MBR-1",
            rendering_provider_npi="1234567890",
            billing_provider_npi="9999999999",
            date_of_service=date(2026, 2, 1),
            procedure_code="J0135",
            billed_amount=Decimal("500.00"),
            status="received",
            ndc="12345678901",
        )
        db_session.add(claim)
        db_session.commit()

        is_340b, _ = svc.evaluate_claim(claim)
        assert is_340b is False


class TestUnifiedSpendFilters:
    def test_list_spend_by_benefit_type(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc="99999999991", drug_name="Test Drug",
            dos=date(2026, 5, 1),
            billed_amount=Decimal("100.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        items, total = svc.list_spend(tenant_id, benefit_type="pharmacy")
        assert all(r.benefit_type == "pharmacy" for r in items)

    def test_list_spend_by_member_id(self, db_session, tenant_id, member_id):
        svc = UnifiedDrugSpendService(db_session)
        pharm_id = uuid.uuid4()
        svc.record_pharmacy_claim(
            tenant_id=tenant_id, pharmacy_claim_id=pharm_id,
            member_id=member_id, member_id_display="MBR",
            ndc="99999999992", drug_name="Test Drug 2",
            dos=date(2026, 5, 1),
            billed_amount=Decimal("200.00"), allowed_amount=None,
            paid_amount=None, patient_pay=None, quantity=None, days_supply=None,
        )
        items, _ = svc.list_spend(tenant_id, member_id=member_id)
        assert all(r.member_id == member_id for r in items)
