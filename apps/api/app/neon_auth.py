"""Verify managed identity before issuing a bounded, revocable application session."""

import secrets
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LoginSession, User
from app.schemas import SessionOut, UserOut
from app.security import COOKIE, audit, token_hash


@lru_cache(maxsize=4)
def key_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=10)


def verified_claims(token: str) -> dict[str, object]:
    settings = get_settings()
    if not settings.neon_auth_base_url or not settings.neon_auth_jwks_url:
        raise HTTPException(503, "Neon Auth is not configured")
    parsed = urlsplit(settings.neon_auth_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    try:
        key = key_client(settings.neon_auth_jwks_url).get_signing_key_from_jwt(token)
        claims: dict[str, object] = jwt.decode(
            token,
            key.key,
            algorithms=["EdDSA"],
            issuer=origin,
            audience=origin,
            # Managed and local clocks can differ slightly when a token is freshly issued.
            leeway=5,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        expiry = claims["exp"]
        if not isinstance(expiry, (int, float)) or expiry <= datetime.now(UTC).timestamp():
            raise HTTPException(401, "Invalid or expired Neon sign-in")
        if not isinstance(claims["sub"], str) or claims.get("banned") is True:
            raise HTTPException(401, "Invalid managed identity")
        return claims
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Neon Auth is temporarily unavailable") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid or expired Neon sign-in") from exc


def exchange(db: Session, request: Request, response: Response, token: str) -> SessionOut:
    claims = verified_claims(token)
    # Never auto-link by email or trust a provider role as workspace administration.
    user = db.scalar(select(User).where(User.neon_subject == claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(403, "Your Neon account needs workspace access from an administrator")
    current = datetime.now(UTC)
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(
            update(LoginSession)
            .where(LoginSession.token_hash == token_hash(old))
            .values(revoked_at=current)
        )
    expiry = claims["exp"]
    if not isinstance(expiry, (int, float)):
        raise HTTPException(401, "Invalid session expiry")
    expires = datetime.fromtimestamp(expiry, UTC)
    session_token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash(session_token),
            csrf_token=csrf,
            expires_at=expires,
        )
    )
    audit(db, user, "auth.neon_login", user.id)
    db.commit()
    response.set_cookie(
        COOKIE,
        session_token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
        max_age=max(0, int((expires - current).total_seconds())),
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf, auth_provider="neon")
