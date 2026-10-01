import pytest
from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.main import app


@pytest.fixture(autouse=True)
def auth_enabled(monkeypatch):
    monkeypatch.setattr(config, "BXK_AUTH_ENABLED", True)
    yield


@pytest.mark.parametrize(
    "path",
    [
        "/product",
        "/support",
        "/application-access",
        "/privacy",
        "/terms",
        "/login",
        "/sms-opt-in",
    ],
)
def test_public_commercial_pages_are_accessible(path):
    response = TestClient(app).get(
        path,
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "text/html" in response.headers.get(
        "content-type",
        "",
    )


def test_authenticated_app_root_redirects_anonymous_user_to_login():
    response = TestClient(app).get(
        "/",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_access_request_listing_is_not_public():
    response = TestClient(app).get(
        "/api/access-requests",
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_admin_support_request_listing_is_not_public():
    response = TestClient(app).get(
        "/api/support-requests",
        follow_redirects=False,
    )

    assert response.status_code == 401
