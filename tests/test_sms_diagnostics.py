from types import SimpleNamespace

import bxk_app.routes.system_settings as route_module
import bxk_app.services.sms_diagnostics_service as service


class DummyTask:
    def __init__(self, done=False):
        self._done = done

    def done(self):
        return self._done


def test_sms_diagnostics_reports_ready(
    monkeypatch,
):
    values = {
        "BXK_SMS_ALERTS_ENABLED": "true",
        "BXK_TWILIO_ACCOUNT_SID": "sid",
        "BXK_TWILIO_AUTH_TOKEN": "token",
        "BXK_TWILIO_FROM_NUMBER": "+15550000000",
        "BXK_ALERT_PHONE": "+15551234567",
    }

    for name, value in values.items():
        monkeypatch.setenv(
            name,
            value,
        )

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        service,
        "normalize_sms_phone",
        lambda phone: phone,
    )

    monkeypatch.setattr(
        service,
        "has_active_sms_consent",
        lambda phone: True,
    )

    monkeypatch.setattr(
        service,
        "_alert_history",
        lambda: {
            "last_successful_alert_at": None,
            "last_successful_alert_state": None,
            "last_successful_alert_scope": None,
            "overnight_state": "GREEN",
            "daytime_worst_state": "ORANGE",
        },
    )

    result = (
        service.get_sms_diagnostics()
    )

    assert result["ready"] is True
    assert (
        result["transport_configured"]
        is True
    )
    assert result["consent_active"] is True
    assert (
        result["recipient_masked"]
        == "***-***-4567"
    )


def test_sms_test_uses_bxk_sms_path(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "get_sms_diagnostics",
        lambda: {
            "alerts_enabled": True,
            "transport_configured": True,
            "database_configured": True,
            "consent_active": True,
            "recipient_masked":
                "***-***-4567",
        },
    )

    sent = []

    monkeypatch.setattr(
        service,
        "send_bxk_sms",
        sent.append,
    )

    result = service.send_test_sms()

    assert result["sent"] is True
    assert len(sent) == 1
    assert "BXK TRADER PRO TEST" in sent[0]
    assert (
        "SMS alert path is working."
        in sent[0]
    )


def test_sms_diagnostics_reports_tasks(
    monkeypatch,
):
    monkeypatch.setattr(
        route_module,
        "get_sms_diagnostics",
        lambda: {
            "ready": True,
        },
    )

    state = SimpleNamespace(
        daytime_alert_task=
            DummyTask(done=False),
        overnight_alert_task=
            DummyTask(done=False),
    )

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=state,
        )
    )

    result = (
        route_module.sms_diagnostics(
            request
        )
    )

    assert (
        result[
            "daytime_monitor_active"
        ]
        is True
    )

    assert (
        result[
            "overnight_monitor_active"
        ]
        is True
    )


def test_system_settings_has_sms_controls():
    from pathlib import Path

    source = Path(
        "static/system-settings.js"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "/api/sms-diagnostics" in source
    assert "/api/sms-test" in source
    assert "bxkTestSmsButton" in source
    assert "Daytime Monitor" in source
    assert "Overnight Monitor" in source
    assert "Last Successful Alert" in source
