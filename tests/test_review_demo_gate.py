import pytest
from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.main import app


@pytest.fixture(autouse=True)
def restore_demo_flag(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_REVIEW_DEMO_ENABLED",
        False,
    )
    yield


def test_review_demo_is_hidden_by_default():
    response = TestClient(app).get(
        "/review-demo",
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_review_demo_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_REVIEW_DEMO_ENABLED",
        True,
    )

    response = TestClient(app).get(
        "/review-demo",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "DEMO PREVIEW ONLY" in response.text
