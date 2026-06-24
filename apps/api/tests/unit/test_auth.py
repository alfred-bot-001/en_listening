from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from listenflow.core.config import Settings, get_settings
from listenflow.modules.auth.routes import router as auth_router
from listenflow.modules.auth.security import (
    create_access_token,
    decode_token,
    require_auth,
    verify_credentials,
)


def _settings() -> Settings:
    return Settings(
        secret_key="test-secret",
        auth_username="alice",
        auth_password="s3cret",
    )


def test_token_roundtrip() -> None:
    settings = _settings()
    token = create_access_token("alice", settings)
    assert decode_token(token, settings) == "alice"


def test_decode_rejects_tampered_token() -> None:
    settings = _settings()
    token = create_access_token("alice", settings)
    with pytest.raises(Exception):  # noqa: B017 - HTTPException 401
        decode_token(token + "x", settings)


def test_verify_credentials() -> None:
    settings = _settings()
    assert verify_credentials("alice", "s3cret", settings)
    assert not verify_credentials("alice", "wrong", settings)
    assert not verify_credentials("bob", "s3cret", settings)


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = _settings()
    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/protected")
    def protected(user: str = Depends(require_auth)) -> dict[str, str]:
        return {"user": user}

    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client


def test_login_success_and_access_protected(client: TestClient) -> None:
    res = client.post(
        "/api/auth/login", json={"username": "alice", "password": "s3cret"}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert res.json()["username"] == "alice"

    me = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"user": "alice"}


def test_login_wrong_password(client: TestClient) -> None:
    res = client.post(
        "/api/auth/login", json={"username": "alice", "password": "nope"}
    )
    assert res.status_code == 401


def test_protected_requires_token(client: TestClient) -> None:
    assert client.get("/protected").status_code == 401
    bad = client.get("/protected", headers={"Authorization": "Bearer not.a.token"})
    assert bad.status_code == 401
