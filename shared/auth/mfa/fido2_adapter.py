"""shared.auth.mfa.fido2_adapter — FIDO2/WebAuthn registration and authentication.

Thin adapter over the ``fido2`` library's Fido2Server. RP ID and origin are
read from settings. Credentials are stored as dataclasses and persisted in
core.user_fido2_credentials by the service layer.

NEVER log raw assertion responses or public keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialType,
    UserVerificationRequirement,
)

__all__ = [
    "Fido2Settings",
    "Credential",
    "VerifiedCredential",
    "Fido2Adapter",
    "get_fido2_adapter",
]


@dataclass(frozen=True)
class Fido2Settings:
    """Relying-party configuration (injected from app settings)."""

    rp_id: str
    rp_name: str
    origin: str


@dataclass(frozen=True)
class Credential:
    """Stored credential after a successful registration ceremony."""

    credential_id: bytes
    public_key: bytes  # CBOR-encoded COSE public key
    sign_count: int


@dataclass(frozen=True)
class VerifiedCredential:
    """Result of a successful authentication ceremony."""

    credential_id: bytes
    new_sign_count: int


class Fido2Adapter:
    """Wraps Fido2Server with a minimal, testable interface.

    Args:
        settings: RP configuration.
    """

    def __init__(self, settings: Fido2Settings) -> None:
        self._settings = settings
        rp = PublicKeyCredentialRpEntity(
            id=settings.rp_id,
            name=settings.rp_name,
        )
        self._server = Fido2Server(rp)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def begin_registration(
        self,
        user_id: bytes,
        user_name: str,
        user_display_name: str,
        existing_credentials: list[bytes] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Begin a WebAuthn registration ceremony.

        Args:
            user_id: Opaque user handle (e.g. UUID bytes).
            user_name: User identifier (email).
            user_display_name: Human-readable name.
            existing_credentials: List of existing credential_id bytes to
                exclude (prevents re-registration of the same key).

        Returns:
            (PublicKeyCredentialCreationOptions, state_dict)
        """
        exclude: list[PublicKeyCredentialDescriptor] = []
        for cred_id in (existing_credentials or []):
            exclude.append(
                PublicKeyCredentialDescriptor(
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                    id=cred_id,
                )
            )
        options, state = self._server.register_begin(
            {
                "id": user_id,
                "name": user_name,
                "displayName": user_display_name,
            },
            credentials=exclude if exclude else None,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return options, state

    def complete_registration(
        self,
        state: dict[str, Any],
        client_response: AuthenticatorAttestationResponse,
    ) -> Credential:
        """Complete the registration ceremony and return a Credential.

        Args:
            state: The state blob returned by begin_registration.
            client_response: The authenticator's attestation response.

        Returns:
            Credential dataclass ready for storage.

        Raises:
            ValueError: If attestation verification fails.
        """
        auth_data = self._server.register_complete(state, client_response)
        cred: AttestedCredentialData = auth_data.credential_data
        return Credential(
            credential_id=bytes(cred.credential_id),
            public_key=bytes(cred.public_key),
            sign_count=auth_data.counter,
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def begin_authentication(
        self,
        existing_credentials: list[bytes],
    ) -> tuple[Any, dict[str, Any]]:
        """Begin a WebAuthn authentication ceremony.

        Args:
            existing_credentials: List of credential_id bytes registered for
                the user.

        Returns:
            (PublicKeyCredentialRequestOptions, state_dict)
        """
        descriptors = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=cred_id,
            )
            for cred_id in existing_credentials
        ]
        options, state = self._server.authenticate_begin(
            credentials=descriptors,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return options, state

    def complete_authentication(
        self,
        state: dict[str, Any],
        client_response: AuthenticatorAssertionResponse,
        stored_credentials: list[Credential],
    ) -> VerifiedCredential:
        """Complete the authentication ceremony.

        Args:
            state: The state blob returned by begin_authentication.
            client_response: The authenticator's assertion response.
            stored_credentials: All credentials registered for the user (for
                public-key lookup).

        Returns:
            VerifiedCredential with the updated sign_count.

        Raises:
            ValueError: If assertion verification fails or sign_count rollback
                is detected (replay attack).
        """
        # Build AttestedCredentialData list for the server
        attested = []
        cred_map: dict[bytes, Credential] = {}
        for sc in stored_credentials:
            acd = AttestedCredentialData.create(
                aaguid=b"\x00" * 16,
                credential_id=sc.credential_id,
                public_key=sc.public_key,
            )
            attested.append(acd)
            cred_map[bytes(sc.credential_id)] = sc

        auth_data = self._server.authenticate_complete(
            state,
            attested,
            client_response,
        )

        used_id = bytes(auth_data.credential_id)
        new_count = auth_data.counter
        stored = cred_map.get(used_id)
        if stored is None:
            raise ValueError(f"Unknown credential id: {used_id!r}")

        # Replay attack detection: sign_count must advance (or stay 0 for
        # authenticators that don't implement it).
        if new_count != 0 and new_count <= stored.sign_count:
            raise ValueError(
                f"sign_count rollback detected: stored={stored.sign_count}, "
                f"received={new_count}. Possible replay attack."
            )

        return VerifiedCredential(
            credential_id=used_id,
            new_sign_count=new_count,
        )


# ---------------------------------------------------------------------------
# Process-level singleton (configured at startup)
# ---------------------------------------------------------------------------

_adapter: Fido2Adapter | None = None


def configure_fido2(settings: Fido2Settings) -> None:
    """Set the process-wide Fido2Adapter (call once at startup)."""
    global _adapter
    _adapter = Fido2Adapter(settings)


def get_fido2_adapter() -> Fido2Adapter:
    """Return the configured Fido2Adapter.

    Raises:
        RuntimeError: if configure_fido2() has not been called.
    """
    if _adapter is None:
        raise RuntimeError("FIDO2 not configured: call configure_fido2() at startup")
    return _adapter
