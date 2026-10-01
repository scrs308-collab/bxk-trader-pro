import pytest
from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.main import app


@pytest.fixture(autouse=True)
def restore_preview_mode(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_PREVIEW_MODE",
        False,
    )
    yield


def test_preview_mode_adds_noindex_headers(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_PREVIEW_MODE",
        True,
    )

    response = TestClient(app).get(
        "/product",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert (
        response.headers["X-Robots-Tag"]
        == "noindex, nofollow, noarchive"
    )
    assert response.headers["Cache-Control"] == "no-store"


def test_normal_mode_does_not_force_preview_headers():
    response = TestClient(app).get(
        "/product",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "X-Robots-Tag" not in response.headers
