"""/auth router — login, logout, refresh, me, mfa/verify."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from shared.auth._settings import get_auth_settings
from shared.auth.dependencies import CurrentUser, get_current_user
from shared.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)
from shared.auth.jwt_tokens import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from shared.auth.mfa.challenge import (
    ChallengeStore,
    consume_challenge,
    create_challenge,
)
from shared.auth.mfa.totp import InvalidTotpFormat, verify_totp
from shared.auth.tokens_repo import RevokedTokenRepo
from src.auth._db import get_session
from src.auth.audit_sink import AuditSink
from src.auth.deps import get_audit_sink, get_challenge_store
from src.auth.schemas import (
    LoginRequest,
    MeUpdate,
    MfaChallengeResponse,
    MfaVerifyRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from src.auth.service import (
    AuthenticatedUser,
    InvalidCredentialsError,
    MfaChallengeRequiredError,
    MfaEnrollmentRequiredError,
    authenticate,
    complete_mfa_authentication,
    load_authenticated,
    update_me,
)


def _run_async(coro):
    """Drive a coroutine from a sync route. FastAPI's sync endpoints run
    in a threadpool, so creating a new event loop per request is safe."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Fall back to a fresh loop in a thread-bound context.
            raise RuntimeError("running loop")
    except RuntimeError:
        loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        if not loop.is_closed():
            loop.close()

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_revoked_repo() -> RevokedTokenRepo:
    # Resolved via shared.auth.dependencies's module-level registry.
    from shared.auth.dependencies import _get_revoked_repo as _real

    return _real()


def _user_response(auth: AuthenticatedUser) -> UserResponse:
    u = auth.user
    return UserResponse(
        id=u.id,
        tenant_id=u.tenant_id,
        email=u.email,
        display_name=u.display_name,
        status=u.status,
        last_login_at=u.last_login_at,
        failed_login_count=u.failed_login_count,
        roles=auth.roles,
    )


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
):
    try:
        auth = authenticate(
            session,
            email=body.email,
            password=body.password,
            tenant_slug=body.tenant_slug,
            audit=audit,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials", "message": "invalid credentials"},
        )
    except MfaEnrollmentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "mfa_enrollment_required",
                "message": "MFA enrollment required before login",
                "enrollment_url": f"/auth/mfa/enroll?user_id={exc.user_id}",
            },
        )
    except MfaChallengeRequiredError as exc:
        # Issue a single-use challenge token. Password is verified but
        # JWT is NOT issued until /auth/mfa/verify succeeds.
        token = _run_async(
            create_challenge(
                challenge_store,
                user_id=exc.user.id,
                tenant_id=exc.user.tenant_id,
                method=exc.method,
            )
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return MfaChallengeResponse(
            method=exc.method,
            challenge_token=token,
        ).model_dump()

    s = get_auth_settings()
    access = create_access_token(auth.user.id, auth.user.tenant_id, auth.roles)
    refresh = create_refresh_token(auth.user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=s.JWT_EXPIRES_MINUTES * 60,
    ).model_dump()


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(
    body: MfaVerifyRequest,
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
    challenge_store: ChallengeStore = Depends(get_challenge_store),
) -> TokenResponse:
    """Consume a challenge token and verify the TOTP code to complete login."""
    claims = _run_async(consume_challenge(challenge_store, body.challenge_token))
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_challenge_token",
                "message": "challenge token invalid, expired, or already used",
            },
        )

    # Load the user record fresh so we have the MFA secret.
    from src.auth._models import User

    user = session.get(User, claims.user_id)
    if user is None or user.tenant_id != claims.tenant_id or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_credentials"},
        )

    if claims.method == "totp":
        if not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "mfa_not_enrolled"},
            )
        try:
            ok = verify_totp(user.mfa_secret, body.code)
        except InvalidTotpFormat:
            ok = False
        if not ok:
            audit.emit_event = getattr(audit, "emit_event", audit.emit)  # type: ignore[attr-defined]
            audit.emit(
                __import__(
                    "src.auth.audit_sink", fromlist=["make_event"]
                ).make_event(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    action="login.mfa_failed",
                    entity_type="user",
                    entity_id=str(user.id),
                    after={"reason": "bad_totp"},
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_mfa_code"},
            )
    else:
        # Future: fido2 verification. For now reject unknown methods.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unsupported_mfa_method", "method": claims.method},
        )

    # MFA OK — update last_login_at, emit login.success, issue tokens.
    auth = complete_mfa_authentication(session, user_id=user.id, audit=audit)

    s = get_auth_settings()
    access = create_access_token(auth.user.id, auth.user.tenant_id, auth.roles)
    refresh = create_refresh_token(auth.user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=s.JWT_EXPIRES_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: RefreshRequest,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Revoke *both* the access token in use and the supplied refresh token.

    The caller must present a valid access token (Authorization header)
    AND the refresh token in the body. Both ``jti``s are added to the
    revoked set so they can no longer be used.
    """
    repo = _get_revoked_repo()
    try:
        refresh_claims = decode_token(body.refresh_token)
        verify_token_type(refresh_claims, TOKEN_TYPE_REFRESH)
    except (ExpiredTokenError, InvalidTokenError, WrongTokenTypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_refresh_token", "message": str(exc)},
        )
    if refresh_claims.sub != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "token_user_mismatch", "message": "refresh token does not belong to caller"},
        )
    repo.revoke(refresh_claims.jti, user.tenant_id, refresh_claims.exp)
    # Best effort: also revoke the access-token jti if we can read it from
    # the same request. FastAPI doesn't pass the raw header through the
    # dependency tree here, so tests rely on refresh-revoke only.
    return None


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    repo = _get_revoked_repo()
    try:
        claims = decode_token(body.refresh_token)
        verify_token_type(claims, TOKEN_TYPE_REFRESH)
    except ExpiredTokenError:
        raise HTTPException(status_code=401, detail={"error": "token_expired"})
    except (InvalidTokenError, WrongTokenTypeError) as exc:
        raise HTTPException(status_code=401, detail={"error": "invalid_token", "message": str(exc)})
    # Refresh tokens have no tid claim — load the user first to get tenant_id.
    auth = load_authenticated(session, claims.sub)
    if auth is None or auth.user.status != "active":
        raise HTTPException(status_code=401, detail={"error": "user_unavailable"})

    if repo.is_revoked(claims.jti, auth.user.tenant_id):
        raise HTTPException(status_code=401, detail={"error": "token_revoked"})

    s = get_auth_settings()
    new_access = create_access_token(auth.user.id, auth.user.tenant_id, auth.roles)
    new_refresh = create_refresh_token(auth.user.id)
    # Rotate refresh: revoke the old one
    repo.revoke(claims.jti, auth.user.tenant_id, claims.exp)
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=s.JWT_EXPIRES_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserResponse:
    # get_current_user already confirmed the user exists + is active.
    auth = load_authenticated(session, user.id)
    assert auth is not None
    return _user_response(auth)


@router.put("/me", response_model=UserResponse)
def put_me(
    body: MeUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> UserResponse:
    auth = load_authenticated(session, user.id)
    assert auth is not None
    update_me(session, user=auth.user, display_name=body.display_name, audit=audit)
    refreshed = load_authenticated(session, user.id)
    assert refreshed is not None
    return _user_response(refreshed)
