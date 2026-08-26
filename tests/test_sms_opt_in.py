from fastapi.testclient import TestClient

from bxk_app import auth_middleware
from bxk_app.main import app

import bxk_app.routes.sms_consent as consent_route


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


def test_sms_opt_in_requires_affirmative_consent(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_middleware.config,
        "BXK_AUTH_ENABLED",
        True,
    )

    client = TestClient(app)

    response = client.post(
        "/api/sms/opt-in",
        json={
            "phone_number":
                "(252) 318-7111",
            "consent": False,
        },
    )

    assert response.status_code == 400


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
        phone_number,
    ):
        captured["phone"] = phone_number

        return {
            "phone": "***7111",
            "consent_version":
                "test-v1",
            "consented_at":
                "2026-08-26T12:00:00+00:00",
        }

    monkeypatch.setattr(
        consent_route,
        "record_sms_consent",
        fake_record,
    )

    client = TestClient(app)

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
