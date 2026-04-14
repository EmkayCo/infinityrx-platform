"""PHI encryption tests for PharmacyPaymentInfo.

Verifies:
- Encrypted fields round-trip: plaintext written → plaintext read back via ORM.
- Raw DB bytes are ciphertext, not plaintext.
- AES-GCM AAD cross-tenant isolation: ciphertext bound to tenant A's AAD cannot
  be decrypted with tenant B's AAD (DecryptionError).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from shared.crypto.aes import DecryptionError, decrypt, encrypt
from src.models.tables import Pharmacy, PharmacyPaymentInfo

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest_asyncio.fixture
async def pharmacy_for_phi(db_session: AsyncSession) -> Pharmacy:
    p = Pharmacy(
        npi="5551234567",
        nabp_number="5551234",
        legal_name="PHI Test Pharmacy",
        display_name="PHI Test Pharmacy",
        pharmacy_type="retail",
        address_line_1="99 Secure St",
        city="Chicago",
        state="IL",
        zip_code="60601",
        status="active",
    )
    db_session.add(p)
    await db_session.flush()
    return p


class TestPharmacyPaymentInfoEncryption:
    @pytest.mark.asyncio
    async def test_encrypted_fields_round_trip(
        self, db_session: AsyncSession, pharmacy_for_phi: Pharmacy
    ) -> None:
        """ORM transparently encrypts on write and decrypts on read."""
        info = PharmacyPaymentInfo(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_for_phi.id,
            bank_name="First National Bank",
            routing_number="021000021",
            account_number="9876543210",
            account_type="checking",
            tax_id="12-3456789",
        )
        db_session.add(info)
        await db_session.flush()

        await db_session.refresh(info)

        assert info.bank_name == "First National Bank"
        assert info.routing_number == "021000021"
        assert info.account_number == "9876543210"
        assert info.tax_id == "12-3456789"

    @pytest.mark.asyncio
    async def test_raw_db_bytes_are_ciphertext_not_plaintext(
        self, db_session: AsyncSession, pharmacy_for_phi: Pharmacy
    ) -> None:
        """Raw bytes stored in DB must not contain the plaintext routing number.

        Uses type_coerce(col, LargeBinary) to bypass the EncryptedString TypeDecorator
        and read the raw encrypted blob directly from the DB.
        """
        from sqlalchemy import LargeBinary, select as _select, type_coerce
        from src.models.tables import PharmacyPaymentInfo as _PPI

        info = PharmacyPaymentInfo(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_for_phi.id,
            routing_number="021000021",
        )
        db_session.add(info)
        await db_session.flush()

        # Read the raw blob by coercing the column type to LargeBinary,
        # which skips the EncryptedString decrypt step entirely.
        raw_col = type_coerce(_PPI.__table__.c.routing_number, LargeBinary)
        stmt = _select(raw_col).where(_PPI.__table__.c.id == info.id)
        result = await db_session.execute(stmt)
        raw_value = result.scalar_one()

        if isinstance(raw_value, memoryview):
            raw_value = bytes(raw_value)

        # Raw bytes must NOT contain the plaintext — they are encrypted ciphertext
        assert b"021000021" not in raw_value
        # And the blob must be non-empty (something was written)
        assert len(raw_value) > 0

    @pytest.mark.asyncio
    async def test_null_encrypted_field_stays_null(
        self, db_session: AsyncSession, pharmacy_for_phi: Pharmacy
    ) -> None:
        info = PharmacyPaymentInfo(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_for_phi.id,
        )
        db_session.add(info)
        await db_session.flush()
        await db_session.refresh(info)

        assert info.routing_number is None
        assert info.account_number is None
        assert info.tax_id is None


class TestAadCrossTenantIsolation:
    """AES-GCM AAD binds ciphertext to a specific tenant context.

    When payment info is encrypted with tenant A's AAD, decrypting with
    tenant B's AAD raises DecryptionError — preventing cross-tenant data
    access even if the raw bytes are somehow leaked.
    """

    def test_aad_bound_ciphertext_fails_with_wrong_tenant_aad(self) -> None:
        plaintext = b"021000021"
        aad_a = TENANT_A.bytes
        aad_b = TENANT_B.bytes

        ciphertext = encrypt(plaintext, associated_data=aad_a)

        with pytest.raises(DecryptionError):
            decrypt(ciphertext, associated_data=aad_b)

    def test_aad_bound_ciphertext_succeeds_with_correct_tenant_aad(self) -> None:
        plaintext = b"021000021"
        aad_a = TENANT_A.bytes

        ciphertext = encrypt(plaintext, associated_data=aad_a)
        recovered = decrypt(ciphertext, associated_data=aad_a)

        assert recovered == plaintext

    def test_ciphertext_without_aad_fails_when_aad_required(self) -> None:
        plaintext = b"9876543210"
        aad_a = TENANT_A.bytes

        ciphertext_no_aad = encrypt(plaintext)

        with pytest.raises(DecryptionError):
            decrypt(ciphertext_no_aad, associated_data=aad_a)
