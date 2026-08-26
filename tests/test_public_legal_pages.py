from fastapi.testclient import TestClient

from bxk_app import auth_middleware
from bxk_app.main import app


def test_public_legal_pages_bypass_auth(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_middleware.config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = TestClient(app)

    cases = [
        (
            "/privacy",
            "Privacy Policy",
        ),
        (
            "/terms",
            "Terms &amp; Conditions",
        ),
    ]

    for path, expected in cases:
        response = client.get(
            path,
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert expected in response.text
        assert "text/html" in response.headers[
            "content-type"
        ]



def test_login_exposes_public_legal_links():
    client = TestClient(app)

    response = client.get(
        "/login",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert 'href="/privacy"' in response.text
    assert 'href="/terms"' in response.text


def test_privacy_contains_mobile_nonsharing_disclosure():
    client = TestClient(app)

    response = client.get(
        "/privacy",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert (
        "No mobile information will be shared"
        in response.text
    )
    assert (
        "marketing or promotional purposes"
        in response.text
    )
