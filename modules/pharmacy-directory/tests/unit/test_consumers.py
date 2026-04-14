"""Unit tests for event consumers."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from shared.events.types import EventEnvelope

from src.events.consumers import (
    handle_fwa_credentialing_risk_elevated,
    handle_fwa_pharmacy_risk_elevated,
)


def _make_envelope(event_type: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        correlation_id=uuid.uuid4(),
        source_module="reclaimrx",
        ordering_key="test-key",
        payload=payload,
    )


class TestHandleFwaCredentialingRiskElevated:
    @pytest.mark.asyncio
    async def test_handles_valid_payload(self) -> None:
        envelope = _make_envelope(
            "fwa.credentialing_risk_elevated",
            {
                "application_id": str(uuid.uuid4()),
                "risk_score": 75,
                "risk_factors": {"flag": "ownership_change"},
            },
        )
        # Should not raise
        await handle_fwa_credentialing_risk_elevated(envelope)

    @pytest.mark.asyncio
    async def test_warns_on_missing_application_id(self) -> None:
        envelope = _make_envelope(
            "fwa.credentialing_risk_elevated",
            {"risk_score": 75},
        )
        with patch("src.events.consumers.logger") as mock_logger:
            await handle_fwa_credentialing_risk_elevated(envelope)
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_warns_on_missing_risk_score(self) -> None:
        envelope = _make_envelope(
            "fwa.credentialing_risk_elevated",
            {"application_id": str(uuid.uuid4())},
        )
        with patch("src.events.consumers.logger") as mock_logger:
            await handle_fwa_credentialing_risk_elevated(envelope)
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_info_on_success(self) -> None:
        envelope = _make_envelope(
            "fwa.credentialing_risk_elevated",
            {
                "application_id": str(uuid.uuid4()),
                "risk_score": 60,
                "risk_factors": {},
            },
        )
        with patch("src.events.consumers.logger") as mock_logger:
            await handle_fwa_credentialing_risk_elevated(envelope)
            mock_logger.info.assert_called_once()


class TestHandleFwaPharmacyRiskElevated:
    @pytest.mark.asyncio
    async def test_handles_valid_payload(self) -> None:
        envelope = _make_envelope(
            "fwa.pharmacy_risk_elevated",
            {
                "pharmacy_id": str(uuid.uuid4()),
                "npi": "1234567890",
            },
        )
        # Should not raise
        await handle_fwa_pharmacy_risk_elevated(envelope)

    @pytest.mark.asyncio
    async def test_warns_on_missing_pharmacy_id(self) -> None:
        envelope = _make_envelope(
            "fwa.pharmacy_risk_elevated",
            {"npi": "1234567890"},
        )
        with patch("src.events.consumers.logger") as mock_logger:
            await handle_fwa_pharmacy_risk_elevated(envelope)
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_info_on_success(self) -> None:
        envelope = _make_envelope(
            "fwa.pharmacy_risk_elevated",
            {
                "pharmacy_id": str(uuid.uuid4()),
                "npi": "9876543210",
            },
        )
        with patch("src.events.consumers.logger") as mock_logger:
            await handle_fwa_pharmacy_risk_elevated(envelope)
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_payload_without_npi(self) -> None:
        envelope = _make_envelope(
            "fwa.pharmacy_risk_elevated",
            {"pharmacy_id": str(uuid.uuid4())},
        )
        # npi=None is fine — should not raise
        await handle_fwa_pharmacy_risk_elevated(envelope)
