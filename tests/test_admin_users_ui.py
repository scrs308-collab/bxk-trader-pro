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
    assert "./admin-users.js?v=1" in text


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
