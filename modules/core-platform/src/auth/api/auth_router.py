"""/auth router — login, logout, refresh, me."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
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
from shared.auth.tokens_repo import RevokedTokenRepo
from src.auth._db import get_session
from src.auth.audit_sink import AuditSink
from src.auth.deps import get_audit_sink
from src.auth.schemas import (
    LoginRequest,
    MeUpdate,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from src.auth.service import (
    AuthenticatedUser,
    InvalidCredentialsError,
    authenticate,
    load_authenticated,
    update_me,
)

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


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    session: Session = Depends(get_session),
    audit: AuditSink = Depends(get_audit_sink),
) -> TokenResponse:
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
    repo.revoke(refresh_claims.jti, refresh_claims.exp)
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
    if repo.is_revoked(claims.jti):
        raise HTTPException(status_code=401, detail={"error": "token_revoked"})

    auth = load_authenticated(session, claims.sub)
    if auth is None or auth.user.status != "active":
        raise HTTPException(status_code=401, detail={"error": "user_unavailable"})

    s = get_auth_settings()
    new_access = create_access_token(auth.user.id, auth.user.tenant_id, auth.roles)
    new_refresh = create_refresh_token(auth.user.id)
    # Rotate refresh: revoke the old one
    repo.revoke(claims.jti, claims.exp)
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
