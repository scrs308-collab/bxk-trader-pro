import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
from bxk_app.routes import billing as billing_routes
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def configure_auth(
    monkeypatch,
    session_factory,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )
    monkeypatch.setattr(
        config,
        "BXK_SESSION_SECRET",
        "a" * 64,
    )
    monkeypatch.setattr(
        config,
        "BXK_SESSION_TTL_SECONDS",
        3600,
    )
    monkeypatch.setattr(
        config,
        "BXK_AUTH_COOKIE_SECURE",
        False,
    )
    monkeypatch.setattr(
        auth_service,
        "database_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        auth_service,
        "get_session_factory",
        lambda: session_factory,
    )

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = (
        override_get_db
    )


def add_beta(session_factory):
    with session_factory() as session:
        user = User(
            username="billing-beta",
            email="billing-beta@example.com",
            password_hash=hash_app_password(
                "Password123!"
            ),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        session.commit()
        return str(user.id)


def client_with_user(user_id):
    client = TestClient(app)
    token = (
        auth_service
        .create_database_session_token(user_id)
    )
    client.cookies.set(
        auth_service.SESSION_COOKIE_NAME,
        token,
    )
    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_billing_status_requires_authentication(
    monkeypatch,
):
    factory = make_session_factory()
    configure_auth(monkeypatch, factory)

    response = TestClient(app).get(
        "/api/billing/status"
    )

    assert response.status_code == 401


def test_authenticated_user_can_view_billing_status(
    monkeypatch,
):
    factory = make_session_factory()
    beta_id = add_beta(factory)
    configure_auth(monkeypatch, factory)
    monkeypatch.setattr(
        config,
        "BXK_BILLING_ENABLED",
        False,
    )

    response = client_with_user(beta_id).get(
        "/api/billing/status"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["billing"]["enabled"] is False
    assert body["can_manage_billing"] is False
    assert body["subscription"][
        "access_reason"
    ] in {
        "ENFORCEMENT_DISABLED",
        "NO_SUBSCRIPTION",
    }


def test_checkout_uses_authenticated_database_user(
    monkeypatch,
):
    factory = make_session_factory()
    beta_id = add_beta(factory)
    configure_auth(monkeypatch, factory)
    captured = {}

    def fake_checkout(
        session,
        *,
        user,
        interval,
        request_token,
    ):
        captured.update(
            user_id=str(user.id),
            interval=interval,
            request_token=request_token,
        )
        return {
            "checkout_session_id": "cs_route",
            "url": "https://checkout.stripe.test/route",
        }

    monkeypatch.setattr(
        billing_routes,
        "create_checkout_session",
        fake_checkout,
    )

    token = str(uuid.uuid4())
    response = client_with_user(beta_id).post(
        "/api/billing/checkout-session",
        json={
            "interval": "ANNUAL",
            "request_token": token,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "user_id": beta_id,
        "interval": "ANNUAL",
        "request_token": token,
    }


def test_webhook_is_public_but_still_processed(
    monkeypatch,
):
    factory = make_session_factory()
    configure_auth(monkeypatch, factory)
    captured = {}

    def fake_construct(payload, signature):
        captured["payload"] = payload
        captured["signature"] = signature
        return {
            "id": "evt_route",
            "type": "customer.subscription.updated",
            "data": {"object": {}},
        }

    def fake_process(session, *, event, payload):
        captured["event"] = event
        return {
            "processed": True,
            "duplicate": False,
            "outcome": "TESTED",
        }

    monkeypatch.setattr(
        billing_routes,
        "construct_stripe_event",
        fake_construct,
    )
    monkeypatch.setattr(
        billing_routes,
        "process_stripe_webhook",
        fake_process,
    )

    response = TestClient(app).post(
        "/api/billing/webhook",
        content=b"stripe-body",
        headers={
            "Stripe-Signature": "test-signature",
        },
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "TESTED"
    assert captured["payload"] == b"stripe-body"
    assert captured["signature"] == (
        "test-signature"
    )


def test_subscription_page_is_protected(
    monkeypatch,
):
    factory = make_session_factory()
    configure_auth(monkeypatch, factory)

    response = TestClient(app).get(
        "/subscription",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_authenticated_subscription_page_loads(
    monkeypatch,
):
    factory = make_session_factory()
    beta_id = add_beta(factory)
    configure_auth(monkeypatch, factory)

    response = client_with_user(beta_id).get(
        "/subscription",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "BXK Trader Pro Billing" in response.text
    assert "Choose Monthly" in response.text
    assert "Manage Billing" in response.text
