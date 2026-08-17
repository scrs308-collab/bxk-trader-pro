import pytest
from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


@pytest.fixture
def configured_auth(monkeypatch):
    username = "joe"
    password = "StrongPass123!"

    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        username,
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        hash_app_password(password),
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_SECRET",
        "a" * 64,
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_TTL_SECONDS",
        3600,
    )

    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        False,
    )

    monkeypatch.setattr(
        config,
        "BXK_AUTH_COOKIE_SECURE",
        False,
    )

    return {
        "username": username,
        "password": password,
    }


def test_session_token_round_trip(
    configured_auth,
):
    token = auth_service.create_session_token(
        configured_auth["username"],
        now=1000,
    )

    result = (
        auth_service.verify_session_token(
            token,
            now=1001,
        )
    )

    assert result is not None
    assert (
        result["username"]
        == configured_auth["username"]
    )


def test_tampered_session_is_rejected(
    configured_auth,
):
    token = auth_service.create_session_token(
        configured_auth["username"],
        now=1000,
    )

    payload, signature = token.split(
        ".",
        1,
    )

    tampered = (
        payload
        + "."
        + signature[:-1]
        + (
            "A"
            if signature[-1] != "A"
            else "B"
        )
    )

    assert (
        auth_service.verify_session_token(
            tampered,
            now=1001,
        )
        is None
    )


def test_expired_session_is_rejected(
    configured_auth,
):
    token = auth_service.create_session_token(
        configured_auth["username"],
        now=1000,
    )

    assert (
        auth_service.verify_session_token(
            token,
            now=5001,
        )
        is None
    )


def test_correct_credentials(
    configured_auth,
):
    assert auth_service.verify_credentials(
        configured_auth["username"],
        configured_auth["password"],
    )


def test_wrong_credentials_rejected(
    configured_auth,
):
    assert not auth_service.verify_credentials(
        configured_auth["username"],
        "wrong-password",
    )

    assert not auth_service.verify_credentials(
        "wrong-user",
        configured_auth["password"],
    )


def test_login_status_logout_flow(
    configured_auth,
):
    client = TestClient(app)

    status = client.get(
        "/api/auth/status"
    )

    assert status.status_code == 200
    assert (
        status.json()["authenticated"]
        is False
    )

    login = client.post(
        "/api/auth/login",
        json={
            "username": (
                configured_auth["username"]
            ),
            "password": (
                configured_auth["password"]
            ),
        },
    )

    assert login.status_code == 200

    cookie = client.cookies.get(
        auth_service.SESSION_COOKIE_NAME
    )

    assert cookie

    authenticated = client.get(
        "/api/auth/status"
    )

    assert authenticated.status_code == 200
    assert (
        authenticated.json()[
            "authenticated"
        ]
        is True
    )

    assert (
        authenticated.json()["username"]
        == configured_auth["username"]
    )

    logout = client.post(
        "/api/auth/logout"
    )

    assert logout.status_code == 200

    after_logout = client.get(
        "/api/auth/status"
    )

    assert (
        after_logout.json()[
            "authenticated"
        ]
        is False
    )


def test_invalid_login_returns_401(
    configured_auth,
):
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "username": (
                configured_auth["username"]
            ),
            "password": "incorrect",
        },
    )

    assert response.status_code == 401
