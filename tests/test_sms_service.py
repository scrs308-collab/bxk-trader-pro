import urllib.parse

import pytest

from bxk_app.services.sms_service import (
    send_sms,
)


class FakeResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


def test_sms_uses_twilio_https_api(
    monkeypatch,
):
    monkeypatch.setenv(
        "BXK_TWILIO_ACCOUNT_SID",
        "AC123",
    )
    monkeypatch.setenv(
        "BXK_TWILIO_AUTH_TOKEN",
        "secret-token",
    )
    monkeypatch.setenv(
        "BXK_TWILIO_FROM_NUMBER",
        "+15550000001",
    )
    monkeypatch.setenv(
        "BXK_ALERT_PHONE",
        "+15550000002",
    )

    captured = {}

    def fake_urlopen(
        request,
        timeout,
    ):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "urllib.request.urlopen",
        fake_urlopen,
    )

    assert send_sms(
        "BXK test"
    ) is True

    request = captured["request"]

    assert (
        request.full_url
        == (
            "https://api.twilio.com/"
            "2010-04-01/Accounts/"
            "AC123/Messages.json"
        )
    )

    form = urllib.parse.parse_qs(
        request.data.decode("utf-8")
    )

    assert form["To"] == [
        "+15550000002"
    ]
    assert form["From"] == [
        "+15550000001"
    ]
    assert form["Body"] == [
        "BXK test"
    ]

    assert captured["timeout"] == 15


def test_sms_requires_configuration(
    monkeypatch,
):
    for name in [
        "BXK_TWILIO_ACCOUNT_SID",
        "BXK_TWILIO_AUTH_TOKEN",
        "BXK_TWILIO_FROM_NUMBER",
        "BXK_ALERT_PHONE",
    ]:
        monkeypatch.delenv(
            name,
            raising=False,
        )

    with pytest.raises(
        RuntimeError,
        match="configuration is incomplete",
    ):
        send_sms(
            "BXK test"
        )



def test_bxk_sms_blocks_without_consent(
    monkeypatch,
):
    import bxk_app.services.sms_service as sms_service
    import bxk_app.services.sms_consent_service as consent_service

    monkeypatch.setenv(
        "BXK_ALERT_PHONE",
        "+15550000002",
    )

    monkeypatch.setattr(
        consent_service,
        "has_active_sms_consent",
        lambda phone_number: False,
    )

    with pytest.raises(
        RuntimeError,
        match="active consent",
    ):
        sms_service.send_bxk_sms(
            "BXK test"
        )


def test_bxk_sms_sends_after_consent(
    monkeypatch,
):
    import bxk_app.services.sms_service as sms_service
    import bxk_app.services.sms_consent_service as consent_service

    monkeypatch.setenv(
        "BXK_ALERT_PHONE",
        "+15550000002",
    )

    monkeypatch.setattr(
        consent_service,
        "has_active_sms_consent",
        lambda phone_number: True,
    )

    captured = {}

    def fake_send(
        message,
        *,
        recipient=None,
    ):
        captured["message"] = message
        captured["recipient"] = recipient

        return True

    monkeypatch.setattr(
        sms_service,
        "send_sms",
        fake_send,
    )

    assert sms_service.send_bxk_sms(
        "BXK consented test"
    ) is True

    assert (
        captured["recipient"]
        == "+15550000002"
    )

    assert (
        captured["message"]
        == "BXK consented test"
    )
