"""Tests for shared.auth.mfa.fido2_adapter.

FIDO2/WebAuthn relies heavily on hardware authenticator interactions. We test
the adapter's surface area, configuration, singleton management, and error
paths using mocks where needed, and verify real Fido2Server calls for
begin_registration and begin_authentication (no attestation hardware required).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.auth.mfa.fido2_adapter import (
    Credential,
    Fido2Adapter,
    Fido2Settings,
    VerifiedCredential,
    configure_fido2,
    get_fido2_adapter,
)

_SETTINGS = Fido2Settings(
    rp_id="infinityrx.local",
    rp_name="InfinityRx Test",
    origin="https://infinityrx.local",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


def test_fido2_settings_frozen() -> None:
    with pytest.raises(AttributeError):
        _SETTINGS.rp_id = "changed"  # type: ignore[misc]


def test_credential_frozen() -> None:
    cred = Credential(credential_id=b"abc", public_key=b"pk", sign_count=0)
    with pytest.raises(AttributeError):
        cred.sign_count = 99  # type: ignore[misc]


def test_verified_credential_frozen() -> None:
    vc = VerifiedCredential(credential_id=b"abc", new_sign_count=1)
    with pytest.raises(AttributeError):
        vc.new_sign_count = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Adapter construction
# ---------------------------------------------------------------------------


def test_adapter_creates_server() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    assert adapter._server is not None


# ---------------------------------------------------------------------------
# begin_registration — real Fido2Server
# ---------------------------------------------------------------------------


def test_begin_registration_returns_options_and_state() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    options, state = adapter.begin_registration(
        user_id=b"\x01" * 16,
        user_name="test@infinityrx.com",
        user_display_name="Test User",
    )
    assert options is not None
    assert isinstance(state, dict)


def test_begin_registration_with_existing_credentials() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    options, state = adapter.begin_registration(
        user_id=b"\x01" * 16,
        user_name="test@infinityrx.com",
        user_display_name="Test User",
        existing_credentials=[b"\xaa" * 32],
    )
    assert options is not None
    assert isinstance(state, dict)


def test_begin_registration_empty_exclude_list() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    options, state = adapter.begin_registration(
        user_id=b"\x01" * 16,
        user_name="test@infinityrx.com",
        user_display_name="Test User",
        existing_credentials=[],
    )
    assert options is not None


# ---------------------------------------------------------------------------
# begin_authentication — real Fido2Server
# ---------------------------------------------------------------------------


def test_begin_authentication_returns_options_and_state() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    options, state = adapter.begin_authentication(
        existing_credentials=[b"\xbb" * 32],
    )
    assert options is not None
    assert isinstance(state, dict)


def test_begin_authentication_multiple_credentials() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    options, state = adapter.begin_authentication(
        existing_credentials=[b"\x01" * 32, b"\x02" * 32, b"\x03" * 32],
    )
    assert options is not None


# ---------------------------------------------------------------------------
# complete_registration (mocked — requires real authenticator hardware)
# ---------------------------------------------------------------------------


def test_complete_registration_delegates_to_server() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    mock_auth_data = MagicMock()
    mock_cred_data = MagicMock()
    mock_cred_data.credential_id = b"\xcc" * 32
    mock_cred_data.public_key = b"\xdd" * 64
    mock_auth_data.credential_data = mock_cred_data
    mock_auth_data.counter = 0

    with patch.object(adapter._server, "register_complete", return_value=mock_auth_data):
        result = adapter.complete_registration(state={"challenge": "abc"}, client_response=MagicMock())
    assert isinstance(result, Credential)
    assert result.credential_id == b"\xcc" * 32
    assert result.public_key == b"\xdd" * 64
    assert result.sign_count == 0


# ---------------------------------------------------------------------------
# complete_authentication — sign_count
# ---------------------------------------------------------------------------


def _run_complete_auth(
    adapter: Fido2Adapter,
    *,
    returned_cred_id: bytes,
    returned_counter: int,
    stored: list[Credential],
) -> VerifiedCredential:
    """Invoke complete_authentication with AttestedCredentialData.create and
    the server's authenticate_complete both mocked out — real COSE parsing
    requires hardware output we can't fabricate in a pure-python test."""
    mock_auth_data = MagicMock()
    mock_auth_data.credential_id = returned_cred_id
    mock_auth_data.counter = returned_counter
    with patch(
        "shared.auth.mfa.fido2_adapter.AttestedCredentialData.create",
        side_effect=lambda aaguid, credential_id, public_key: MagicMock(
            credential_id=credential_id, public_key=public_key
        ),
    ), patch.object(
        adapter._server, "authenticate_complete", return_value=mock_auth_data
    ):
        return adapter.complete_authentication(
            state={}, client_response=MagicMock(), stored_credentials=stored
        )


def test_complete_authentication_success() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    cred_id = b"\xaa" * 32
    stored = [Credential(credential_id=cred_id, public_key=b"\xbb" * 64, sign_count=3)]
    result = _run_complete_auth(
        adapter, returned_cred_id=cred_id, returned_counter=5, stored=stored
    )
    assert isinstance(result, VerifiedCredential)
    assert result.credential_id == cred_id
    assert result.new_sign_count == 5


def test_complete_authentication_sign_count_zero_allowed() -> None:
    """Authenticators that don't implement sign_count report 0 every time."""
    adapter = Fido2Adapter(_SETTINGS)
    cred_id = b"\xaa" * 32
    stored = [Credential(credential_id=cred_id, public_key=b"\xbb" * 64, sign_count=0)]
    result = _run_complete_auth(
        adapter, returned_cred_id=cred_id, returned_counter=0, stored=stored
    )
    assert result.new_sign_count == 0


def test_complete_authentication_replay_attack_detected() -> None:
    """sign_count rollback (new <= stored, non-zero) raises ValueError."""
    adapter = Fido2Adapter(_SETTINGS)
    cred_id = b"\xaa" * 32
    stored = [Credential(credential_id=cred_id, public_key=b"\xbb" * 64, sign_count=5)]
    with pytest.raises(ValueError, match="sign_count rollback"):
        _run_complete_auth(
            adapter, returned_cred_id=cred_id, returned_counter=3, stored=stored
        )


def test_complete_authentication_sign_count_equal_detected() -> None:
    """sign_count == stored (non-zero) is also a rollback."""
    adapter = Fido2Adapter(_SETTINGS)
    cred_id = b"\xaa" * 32
    stored = [Credential(credential_id=cred_id, public_key=b"\xbb" * 64, sign_count=5)]
    with pytest.raises(ValueError, match="sign_count rollback"):
        _run_complete_auth(
            adapter, returned_cred_id=cred_id, returned_counter=5, stored=stored
        )


def test_complete_authentication_unknown_credential_raises() -> None:
    adapter = Fido2Adapter(_SETTINGS)
    cred_id_returned = b"\xaa" * 32
    cred_id_stored = b"\xbb" * 32  # Different!
    stored = [Credential(credential_id=cred_id_stored, public_key=b"\xcc" * 64, sign_count=0)]
    with pytest.raises(ValueError, match="Unknown credential"):
        _run_complete_auth(
            adapter, returned_cred_id=cred_id_returned, returned_counter=1, stored=stored
        )


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------


def test_get_fido2_adapter_raises_when_not_configured() -> None:
    import shared.auth.mfa.fido2_adapter as mod

    old = mod._adapter
    try:
        mod._adapter = None
        with pytest.raises(RuntimeError, match="FIDO2 not configured"):
            get_fido2_adapter()
    finally:
        mod._adapter = old


def test_configure_fido2_sets_adapter() -> None:
    import shared.auth.mfa.fido2_adapter as mod

    old = mod._adapter
    try:
        mod._adapter = None
        configure_fido2(_SETTINGS)
        adapter = get_fido2_adapter()
        assert isinstance(adapter, Fido2Adapter)
    finally:
        mod._adapter = old
