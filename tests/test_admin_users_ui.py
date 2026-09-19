from pathlib import Path


def test_system_tab_contains_admin_users_card():
    text = Path(
        "static/index.html"
    ).read_text(
        encoding="utf-8"
    )

    assert 'id="adminUsersCard"' in text
    assert 'id="adminUsersPanel"' in text


def test_dashboard_initializes_admin_users():
    text = Path(
        "static/dashboard.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "initializeAdminUsers" in text
    assert "./admin-users.js?v=4" in text


def test_admin_users_checks_owner_role():
    text = Path(
        "static/admin-users.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "/api/auth/status" in text
    assert '"OWNER"' in text


def test_admin_users_uses_management_endpoints():
    text = Path(
        "static/admin-users.js"
    ).read_text(
        encoding="utf-8"
    )

    assert '"/api/admin/users"' in text
    assert 'method: "POST"' in text
    assert 'method: "PATCH"' in text


def test_admin_users_supports_temporary_password():
    text = Path(
        "static/admin-users.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "temporary_password" in text
    assert "generateTemporaryPassword" in text
    assert "crypto.getRandomValues" in text


def test_admin_users_supports_beta_live_trading_control():
    text = Path(
        "static/admin-users.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "live_trading_enabled" in text
    assert "broker-live-trading" in text
    assert "setBrokerLiveTrading" in text
    assert "ENABLE LIVE TRADING" in text
    assert "DISABLE LIVE TRADING" in text
    assert "BROKER REQUIRED" in text
    assert "window.confirm" in text


def test_admin_users_supports_broker_connect_control():
    text = Path(
        "static/admin-users.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "broker_oauth_enabled" in text
    assert "broker-oauth-access" in text
    assert "setBrokerOAuthAccess" in text
    assert "ENABLE BROKER CONNECT" in text
    assert "DISABLE BROKER CONNECT" in text
