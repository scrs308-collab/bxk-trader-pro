import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import hash_app_password


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def configure_auth(monkeypatch, factory):
    monkeypatch.setattr(config, "BXK_AUTH_ENABLED", True)
    monkeypatch.setattr(config, "BXK_SESSION_SECRET", "a" * 64)
    monkeypatch.setattr(config, "BXK_AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "database_configured", lambda: True)
    monkeypatch.setattr(
        auth_service,
        "get_session_factory",
        lambda: factory,
    )

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db


def add_user(factory, role):
    with factory() as session:
        user = User(
            username=f"{role.value.lower()}-readiness",
            email=f"{role.value.lower()}-readiness@example.com",
            password_hash=hash_app_password("Password123!"),
            role=role,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        session.commit()
        return str(user.id)


def client_with_user(user_id):
    client = TestClient(app)
    token = auth_service.create_database_session_token(user_id)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_commercial_readiness_requires_owner(monkeypatch):
    factory = make_session_factory()
    beta_id = add_user(factory, UserRole.BETA)
    configure_auth(monkeypatch, factory)

    response = client_with_user(beta_id).get(
        "/api/admin/commercial-readiness"
    )

    assert response.status_code == 403


def test_owner_can_view_safe_commercial_readiness(monkeypatch):
    factory = make_session_factory()
    owner_id = add_user(factory, UserRole.OWNER)
    configure_auth(monkeypatch, factory)

    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        "test-key",
    )
    monkeypatch.setattr(
        config,
        "BXK_LIVE_TRADING_ENABLED",
        False,
    )
    monkeypatch.setattr(
        config,
        "SCHWAB_CLIENT_ID",
        "client",
    )
    monkeypatch.setattr(
        config,
        "SCHWAB_CLIENT_SECRET",
        "secret",
    )
    monkeypatch.setattr(
        config,
        "SCHWAB_REDIRECT_URI",
        "https://example.test/callback",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_SECRET_KEY",
        "stripe-secret",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_WEBHOOK_SECRET",
        "webhook-secret",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_PRICE_PRO_MONTHLY",
        "price-monthly",
    )
    monkeypatch.setattr(
        config,
        "STRIPE_PRICE_PRO_ANNUAL",
        "",
    )

    response = client_with_user(owner_id).get(
        "/api/admin/commercial-readiness"
    )

    assert response.status_code == 200
    body = response.json()

    assert body["checks"]["authentication_ready"] is True
    assert body["checks"]["broker_secret_storage_ready"] is True
    assert body["checks"]["schwab_oauth_configured"] is True
    assert body["checks"]["stripe_checkout_configured"] is True
    assert body["checks"]["reviewer_safe_mode"] is True

    # The endpoint reports presence/state only and never returns secrets.
    text = response.text
    assert "stripe-secret" not in text
    assert "webhook-secret" not in text
    assert '"client_secret_configured":true' in text
