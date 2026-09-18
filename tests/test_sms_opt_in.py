from fastapi.testclient import TestClient

from bxk_app import auth_middleware
from bxk_app.main import app
from bxk_app.authorization import (
    require_owner_or_beta,
)

import bxk_app.routes.sms_consent as consent_route


TEST_USER_ID = (
    "3f574a3f-f5df-4fa1-b199-3b0eb4c82742"
)


def authenticated_client(monkeypatch):
    user = {
        "user_id": TEST_USER_ID,
        "username": "kdixon",
        "role": "BETA",
    }

    monkeypatch.setattr(
        auth_middleware,
        "verify_session_token",
        lambda token: user,
    )

    app.dependency_overrides[
        require_owner_or_beta
    ] = lambda: user

    client = TestClient(app)
    client.cookies.set(
        "bxk_session",
        "test-session",
    )
    return client


def test_sms_opt_in_page_is_public_and_unchecked(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_middleware.config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = TestClient(app)

    response = client.get(
        "/sms-opt-in",
        follow_redirects=False,
    )

    assert response.status_code == 200

    assert (
        "SMS Trading-Risk Alerts"
        in response.text
    )

    checkbox = response.text.split(
        'id="consentCheckbox"',
        1,
    )[1].split(
        ">",
        1,
    )[0]

    assert "checked" not in checkbox

    assert (
        'href="/privacy"'
        in response.text
    )

    assert (
        'href="/terms"'
        in response.text
    )

    assert (
        'href="/"'
        in response.text
    )


def test_dashboard_links_to_sms_opt_in():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert 'href="/sms-opt-in"' in response.text
    assert "SMS Alerts" in response.text
    assert (
        'data-authenticated-only="true"'
        in response.text
    )


def test_sms_opt_in_requires_affirmative_consent(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_middleware.config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = authenticated_client(
        monkeypatch
    )

    response = client.post(
        "/api/sms/opt-in",
        json={
            "phone_number":
                "(252) 318-7111",
            "consent": False,
        },
    )

    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_sms_opt_in_records_consent(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_middleware.config,
        "BXK_AUTH_ENABLED",
        True,
    )

    captured = {}

    def fake_record(
        *,
        user_id,
        phone_number,
    ):
        captured["phone"] = phone_number
        captured["user_id"] = user_id

        return {
            "phone": "***7111",
            "consent_version":
                "test-v1",
            "consented_at":
                "2026-08-26T12:00:00+00:00",
        }

    monkeypatch.setattr(
        consent_route,
        "record_user_sms_consent",
        fake_record,
    )

    client = authenticated_client(
        monkeypatch
    )

    response = client.post(
        "/api/sms/opt-in",
        json={
            "phone_number":
                "(252) 318-7111",
            "consent": True,
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "OPTED_IN"
    assert result["phone"] == "***7111"

    assert (
        captured["phone"]
        == "(252) 318-7111"
    )

    assert captured["user_id"] == TEST_USER_ID

    app.dependency_overrides.clear()
