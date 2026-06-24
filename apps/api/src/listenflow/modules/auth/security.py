"""JWT helpers and the FastAPI auth dependency for the single configured user."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from listenflow.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def verify_credentials(username: str, password: str, settings: Settings) -> bool:
    """Constant-time check of a login attempt against the configured account."""
    user_ok = secrets.compare_digest(username, settings.auth_username)
    pass_ok = secrets.compare_digest(password, settings.auth_password)
    return user_ok and pass_ok


def create_access_token(username: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> str:
    """Return the subject (username) of a valid token, or raise 401."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _unauthorized("Invalid token payload")
    return subject


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Dependency that enforces a valid Bearer token; returns the username."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Not authenticated")
    return decode_token(credentials.credentials, settings)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
