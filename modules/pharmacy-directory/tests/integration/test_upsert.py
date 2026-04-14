"""Integration tests for NCPDP/NPPES upsert pipeline."""
from __future__ import annotations

import io

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Pharmacy
from src.services.ncpdp_parser import parse_ncpdp_fixture
from src.services.nppes_parser import parse_nppes_fixture
from src.services.upsert import PharmacyUpsertService


NCPDP_CSV = (
    "npi,nabp_number,ncpdp_id,legal_name,dba_name,pharmacy_type,chain_name,chain_code,"
    "store_number,address_line_1,address_line_2,city,state,zip_code,phone,fax,"
    "hours_monday,hours_tuesday,hours_wednesday,hours_thursday,hours_friday,"
    "hours_saturday,hours_sunday,is_24_hour,accepts_electronic_rx,dispenses_controlled,"
    "offers_delivery,offers_compounding,offers_specialty,offers_340b,status\n"
    "1111111119,1111111,111111119,Sunrise Pharmacy,,retail,,,,"
    "50 Elm St,,Boston,MA,02101,6175550001,,09:00-18:00,09:00-18:00,09:00-18:00,"
    "09:00-18:00,09:00-18:00,10:00-14:00,,False,True,True,False,False,False,False,active\n"
)

NPPES_CSV = (
    "NPI,Entity Type Code,Provider Organization Name (Legal Business Name),"
    "Provider Last Name (Legal Name),Provider First Name,"
    "Provider Business Mailing Address First Line,"
    "Provider Business Mailing Address Second Line,"
    "Provider Business Mailing Address City Name,"
    "Provider Business Mailing Address State Name,"
    "Provider Business Mailing Address Postal Code,"
    "Provider Business Practice Location Address First Line,"
    "Provider Business Practice Location Address City Name,"
    "Provider Business Practice Location Address State Name,"
    "Provider Business Practice Location Address Postal Code,"
    "Provider Business Practice Location Address Telephone Number,"
    "Healthcare Provider Taxonomy Code_1,NPI Deactivation Date\n"
    "2222222222,2,New NPPES Pharmacy,,,75 Oak St,,Denver,CO,80201,"
    "75 Oak St,Denver,CO,80201,3035551234,3336S0011X,\n"
)

NPPES_INACTIVE_CSV = (
    "NPI,Entity Type Code,Provider Organization Name (Legal Business Name),"
    "Provider Last Name (Legal Name),Provider First Name,"
    "Provider Business Mailing Address First Line,"
    "Provider Business Mailing Address Second Line,"
    "Provider Business Mailing Address City Name,"
    "Provider Business Mailing Address State Name,"
    "Provider Business Mailing Address Postal Code,"
    "Provider Business Practice Location Address First Line,"
    "Provider Business Practice Location Address City Name,"
    "Provider Business Practice Location Address State Name,"
    "Provider Business Practice Location Address Postal Code,"
    "Provider Business Practice Location Address Telephone Number,"
    "Healthcare Provider Taxonomy Code_1,NPI Deactivation Date\n"
    "3333333333,2,Closed Pharmacy,,,1 Dead End,,Nowhere,AZ,85001,"
    "1 Dead End,Nowhere,AZ,85001,4805550000,333600000X,01/01/2025\n"
)


class TestNcpdpUpsert:
    @pytest.mark.asyncio
    async def test_ncpdp_upsert_creates_pharmacy(self, db_session: AsyncSession) -> None:
        records = parse_ncpdp_fixture(io.StringIO(NCPDP_CSV))
        svc = PharmacyUpsertService(db_session)
        pharmacy, created = await svc.upsert_from_ncpdp(records[0])
        assert created is True
        assert pharmacy.npi == "1111111119"

    @pytest.mark.asyncio
    async def test_ncpdp_upsert_updates_existing_pharmacy(self, db_session: AsyncSession) -> None:
        records = parse_ncpdp_fixture(io.StringIO(NCPDP_CSV))
        svc = PharmacyUpsertService(db_session)
        _, created = await svc.upsert_from_ncpdp(records[0])
        assert created is True
        _, created2 = await svc.upsert_from_ncpdp(records[0])
        assert created2 is False

    @pytest.mark.asyncio
    async def test_ncpdp_sets_ncpdp_last_updated(self, db_session: AsyncSession) -> None:
        records = parse_ncpdp_fixture(io.StringIO(NCPDP_CSV))
        svc = PharmacyUpsertService(db_session)
        pharmacy, _ = await svc.upsert_from_ncpdp(records[0])
        assert pharmacy.ncpdp_last_updated is not None


class TestNppesUpsert:
    @pytest.mark.asyncio
    async def test_nppes_upsert_creates_new_pharmacy(self, db_session: AsyncSession) -> None:
        records = parse_nppes_fixture(io.StringIO(NPPES_CSV))
        svc = PharmacyUpsertService(db_session)
        pharmacy, created = await svc.upsert_from_nppes(records[0])
        assert created is True
        assert pharmacy.npi == "2222222222"

    @pytest.mark.asyncio
    async def test_nppes_classifies_taxonomy(self, db_session: AsyncSession) -> None:
        records = parse_nppes_fixture(io.StringIO(NPPES_CSV))
        svc = PharmacyUpsertService(db_session)
        pharmacy, _ = await svc.upsert_from_nppes(records[0])
        assert pharmacy.pharmacy_type == "specialty"

    @pytest.mark.asyncio
    async def test_nppes_inactive_sets_status(self, db_session: AsyncSession) -> None:
        records = parse_nppes_fixture(io.StringIO(NPPES_INACTIVE_CSV))
        svc = PharmacyUpsertService(db_session)
        pharmacy, _ = await svc.upsert_from_nppes(records[0])
        assert pharmacy.status == "inactive"

    @pytest.mark.asyncio
    async def test_nppes_updates_existing_pharmacy_without_ncpdp(
        self, db_session: AsyncSession
    ) -> None:
        """NPPES should update address/phone when ncpdp_last_updated is None."""
        existing = Pharmacy(
            npi="2222222225",
            legal_name="Old Name",
            display_name="Old Name",
            pharmacy_type="retail",
            address_line_1="Old Address",
            city="Old City",
            state="IL",
            zip_code="60601",
        )
        db_session.add(existing)
        await db_session.flush()

        nppes_csv = (
            "NPI,Entity Type Code,Provider Organization Name (Legal Business Name),"
            "Provider Last Name (Legal Name),Provider First Name,"
            "Provider Business Mailing Address First Line,"
            "Provider Business Mailing Address Second Line,"
            "Provider Business Mailing Address City Name,"
            "Provider Business Mailing Address State Name,"
            "Provider Business Mailing Address Postal Code,"
            "Provider Business Practice Location Address First Line,"
            "Provider Business Practice Location Address City Name,"
            "Provider Business Practice Location Address State Name,"
            "Provider Business Practice Location Address Postal Code,"
            "Provider Business Practice Location Address Telephone Number,"
            "Healthcare Provider Taxonomy Code_1,NPI Deactivation Date\n"
            "2222222225,2,Updated Name,,,100 New St,,New City,NY,10001,"
            "100 New St,New City,NY,10001,2125551234,3336C0003X,\n"
        )
        records = parse_nppes_fixture(io.StringIO(nppes_csv))
        svc = PharmacyUpsertService(db_session)
        pharmacy, created = await svc.upsert_from_nppes(records[0])
        assert created is False
        assert pharmacy.address_line_1 == "100 New St"
        assert pharmacy.city == "New City"

    @pytest.mark.asyncio
    async def test_nppes_does_not_overwrite_ncpdp_address(
        self, db_session: AsyncSession
    ) -> None:
        """NPPES should NOT update address when NCPDP data is already present."""
        from datetime import UTC, datetime
        existing = Pharmacy(
            npi="2222222226",
            legal_name="NCPDP Pharmacy",
            display_name="NCPDP Pharmacy",
            pharmacy_type="retail",
            address_line_1="NCPDP Address",
            city="NCPDP City",
            state="IL",
            zip_code="60601",
            ncpdp_last_updated=datetime.now(UTC),
        )
        db_session.add(existing)
        await db_session.flush()

        nppes_csv = (
            "NPI,Entity Type Code,Provider Organization Name (Legal Business Name),"
            "Provider Last Name (Legal Name),Provider First Name,"
            "Provider Business Mailing Address First Line,"
            "Provider Business Mailing Address Second Line,"
            "Provider Business Mailing Address City Name,"
            "Provider Business Mailing Address State Name,"
            "Provider Business Mailing Address Postal Code,"
            "Provider Business Practice Location Address First Line,"
            "Provider Business Practice Location Address City Name,"
            "Provider Business Practice Location Address State Name,"
            "Provider Business Practice Location Address Postal Code,"
            "Provider Business Practice Location Address Telephone Number,"
            "Healthcare Provider Taxonomy Code_1,NPI Deactivation Date\n"
            "2222222226,2,NPPES Name,,,NPPES Address,,NPPES City,NY,10001,"
            "NPPES Address,NPPES City,NY,10001,2125551234,3336C0003X,\n"
        )
        records = parse_nppes_fixture(io.StringIO(nppes_csv))
        svc = PharmacyUpsertService(db_session)
        pharmacy, created = await svc.upsert_from_nppes(records[0])
        assert created is False
        assert pharmacy.address_line_1 == "NCPDP Address"
