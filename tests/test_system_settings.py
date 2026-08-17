import pytest

from bxk_app.services import (
    system_settings_service as service,
)


BASE_ENV = """TASTYTRADE_USERNAME=legacy-user
TASTYTRADE_PASSWORD=legacy-password
TASTYTRADE_CLIENT_ID=client-id
TASTYTRADE_CLIENT_SECRET=client-secret
TASTYTRADE_REFRESH_TOKEN=refresh-token
TASTYTRADE_ACCOUNT_NUMBER=ABC12345678
TASTYTRADE_BASE_URL=https://api.tastyworks.com
BXK_APP_USERNAME=joe
BXK_APP_PASSWORD_HASH=
BXK_MAX_ORDER_RISK=7500
BXK_MIN_ORDER_CREDIT=1.00
BXK_MIN_REMAINING_BUYING_POWER=15000
BXK_LIVE_TRADING_ENABLED=false
"""


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"

    path.write_text(
        BASE_ENV,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        service,
        "ENV_PATH",
        path,
    )

    return path


def test_get_settings_masks_secrets(
    env_file,
):
    result = service.get_system_settings()

    assert (
        result["tastytrade"][
            "client_secret_configured"
        ]
        is True
    )

    assert (
        result["tastytrade"][
            "refresh_token_configured"
        ]
        is True
    )

    assert (
        result["tastytrade"][
            "account_number_masked"
        ]
        == "*****5678"
    )

    serialized = str(result)

    assert "client-secret" not in serialized
    assert "refresh-token" not in serialized
    assert "legacy-password" not in serialized


def test_blank_secret_preserves_existing_value(
    env_file,
):
    result = service.update_system_settings(
        {
            "tastytrade_client_secret": "",
            "max_order_risk": 9000,
        }
    )

    text = env_file.read_text(
        encoding="utf-8",
    )

    assert (
        "TASTYTRADE_CLIENT_SECRET="
        "client-secret"
        in text
    )

    assert "BXK_MAX_ORDER_RISK=9000" in text

    assert (
        "BXK_LIVE_TRADING_ENABLED=false"
        in text
    )

    assert result["restart_required"] is True


def test_app_password_is_hashed(
    env_file,
):
    service.update_system_settings(
        {
            "app_username": "joe",
            "app_password": "StrongPass123!",
        }
    )

    values = service._read_env_values()

    stored_hash = values[
        "BXK_APP_PASSWORD_HASH"
    ]

    assert "StrongPass123!" not in stored_hash

    assert stored_hash.startswith(
        "pbkdf2_sha256$"
    )

    assert service.verify_app_password(
        "StrongPass123!",
        stored_hash,
    )

    assert not service.verify_app_password(
        "wrong-password",
        stored_hash,
    )


def test_invalid_risk_does_not_modify_file(
    env_file,
):
    before = env_file.read_text(
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        service.update_system_settings(
            {
                "max_order_risk": 0,
            }
        )

    after = env_file.read_text(
        encoding="utf-8",
    )

    assert after == before


def test_live_trading_cannot_be_changed(
    env_file,
):
    with pytest.raises(
        ValueError,
        match="Live trading cannot be changed",
    ):
        service.update_system_settings(
            {
                "live_trading_enabled": True,
            }
        )

    text = env_file.read_text(
        encoding="utf-8",
    )

    assert (
        "BXK_LIVE_TRADING_ENABLED=false"
        in text
    )
