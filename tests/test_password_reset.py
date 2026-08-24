from pathlib import Path

from bxk_app import config
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


def test_temporary_password_works_once(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        "testuser",
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        hash_app_password(
            "PermanentPassword123"
        ),
    )

    auth_service.clear_temporary_password()

    temporary_password = (
        auth_service.issue_temporary_password(
            "testuser",
            ttl_seconds=900,
            now=1000,
        )
    )

    assert temporary_password

    assert auth_service._verify_temporary_password(
        "testuser",
        temporary_password,
        now=1001,
    ) is True

    assert auth_service._verify_temporary_password(
        "testuser",
        temporary_password,
        now=1002,
    ) is False


def test_temporary_password_expires(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_APP_USERNAME",
        "testuser",
    )

    auth_service.clear_temporary_password()

    temporary_password = (
        auth_service.issue_temporary_password(
            "testuser",
            ttl_seconds=15,
            now=1000,
        )
    )

    assert temporary_password

    assert auth_service._verify_temporary_password(
        "testuser",
        temporary_password,
        now=1016,
    ) is False


def test_login_page_has_account_links():
    source = Path(
        "static/login.html"
    ).read_text(encoding="utf-8")

    assert "Forgot Password?" in source
    assert "Create New Account" in source
    assert 'href="/forgot-password"' in source
    assert 'href="/application-access"' in source
