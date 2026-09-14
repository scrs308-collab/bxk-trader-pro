from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.auth_middleware import (
    PUBLIC_PATHS,
)
from bxk_app.main import app


def test_schwab_callback_api_is_public():
    assert (
        "/api/broker-connection/schwab/callback"
        in PUBLIC_PATHS
    )


def test_root_forwards_schwab_authorization_result(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = TestClient(app)

    response = client.get(
        "/?state=test-state&code=test-code",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ] == (
        "/api/broker-connection/"
        "schwab/callback"
        "?state=test-state"
        "&code=test-code"
    )


def test_root_forwards_schwab_error(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = TestClient(app)

    response = client.get(
        (
            "/?state=test-state"
            "&error=access_denied"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        "/api/broker-connection/"
        "schwab/callback"
        in response.headers[
            "location"
        ]
    )


def test_normal_root_still_serves_dashboard(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        False,
    )

    client = TestClient(app)

    response = client.get(
        "/",
        follow_redirects=False,
    )

    assert response.status_code == 200
