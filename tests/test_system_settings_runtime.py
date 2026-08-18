from pathlib import Path

from bxk_app import config
from bxk_app.services import (
    system_settings_service as settings_service,
)


def test_risk_settings_apply_to_runtime(
    monkeypatch,
    tmp_path,
):
    env_path = tmp_path / ".env"

    env_path.write_text(
        (
            "BXK_MAX_ORDER_RISK=7500\n"
            "BXK_MIN_ORDER_CREDIT=1\n"
            "BXK_MIN_REMAINING_BUYING_POWER=15000\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        settings_service,
        "ENV_PATH",
        env_path,
    )

    monkeypatch.setattr(
        config,
        "BXK_MAX_ORDER_RISK",
        7500.0,
    )

    monkeypatch.setattr(
        config,
        "BXK_MIN_ORDER_CREDIT",
        1.0,
    )

    monkeypatch.setattr(
        config,
        "BXK_MIN_REMAINING_BUYING_POWER",
        15000.0,
    )

    result = settings_service.update_system_settings({
        "max_order_risk": 6000,
        "min_order_credit": 1.5,
        "min_remaining_buying_power": 10000,
    })

    assert config.BXK_MAX_ORDER_RISK == 6000.0
    assert config.BXK_MIN_ORDER_CREDIT == 1.5

    assert (
        config.BXK_MIN_REMAINING_BUYING_POWER
        == 10000.0
    )

    assert result["saved"] is True
    assert result["restart_required"] is False


def test_broker_change_resets_authentication(
    monkeypatch,
    tmp_path,
):
    from bxk_app.brokers.tastytrade import broker

    env_path = tmp_path / ".env"

    env_path.write_text(
        (
            "TASTYTRADE_BASE_URL="
            "https://api.tastyworks.com\n"
            "TASTYTRADE_ACCOUNT_NUMBER=OLD1234\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        settings_service,
        "ENV_PATH",
        env_path,
    )

    called = {
        "reset": False,
    }

    def fake_reset():
        called["reset"] = True

    monkeypatch.setattr(
        broker,
        "reset_authentication",
        fake_reset,
    )

    settings_service.update_system_settings({
        "tastytrade_account_number": "NEW7178",
        "tastytrade_base_url":
            "https://api.tastyworks.com",
    })

    assert (
        config.TASTYTRADE_ACCOUNT_NUMBER
        == "NEW7178"
    )

    assert called["reset"] is True
