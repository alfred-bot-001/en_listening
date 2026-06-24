"""Authentication routes: login + current-user check."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from listenflow.core.config import Settings, get_settings
from listenflow.modules.auth.security import (
    create_access_token,
    require_auth,
    verify_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class MeResponse(BaseModel):
    username: str


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    if not verify_credentials(req.username, req.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(req.username, settings)
    return TokenResponse(access_token=token, username=req.username)


@router.get("/me", response_model=MeResponse)
def me(username: Annotated[str, Depends(require_auth)]) -> MeResponse:
    return MeResponse(username=username)
