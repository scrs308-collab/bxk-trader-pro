from fastapi.testclient import TestClient

from bxk_app import config
from bxk_app.main import app
from bxk_app.services import chatbot_service


def test_chat_status_disabled_without_key(monkeypatch):
    monkeypatch.setenv(
        "BXK_CHATBOT_ENABLED",
        "true",
    )
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    response = TestClient(app).get(
        "/api/chat/status"
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_public_chat_returns_answer(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )
    monkeypatch.setenv(
        "BXK_CHATBOT_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    monkeypatch.setattr(
        "bxk_app.routes.chatbot.enforce_rate_limit",
        lambda _key: None,
    )

    monkeypatch.setattr(
        "bxk_app.routes.chatbot.ask_chatbot",
        lambda **kwargs: {
            "answer":
                "BXK Trader Pro is invite-only beta.",
            "model": "test-model",
        },
    )

    response = TestClient(app).post(
        "/api/chat",
        json={
            "message": "What is BXK Trader Pro?",
            "history": [],
            "page_url":
                "https://bxktraderpro.com/",
            "page_title":
                "BXK Trader Pro",
            "page_context":
                "Public product page",
        },
    )

    assert response.status_code == 200
    assert "invite-only" in (
        response.json()["answer"]
    )


def test_chat_rejects_long_message(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        False,
    )

    response = TestClient(app).post(
        "/api/chat",
        json={
            "message": "x" * 2001,
            "history": [],
        },
    )

    assert response.status_code == 422


def test_chat_service_never_requires_private_account_data():
    instructions = chatbot_service.INSTRUCTIONS

    assert (
        "Never imply that you can see"
        in instructions
    )
    assert (
        "Never request passwords"
        in instructions
    )
    assert (
        "Schwab commercial approval"
        in instructions
    )



def test_chat_cors_preflight(monkeypatch):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )

    response = TestClient(app).options(
        "/api/chat",
        headers={
            "Origin":
                "https://bxktraderpro.com",
            "Access-Control-Request-Method":
                "POST",
            "Access-Control-Request-Headers":
                "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "https://bxktraderpro.com"
    )
