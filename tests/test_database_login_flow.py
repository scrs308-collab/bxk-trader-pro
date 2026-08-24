from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
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
        "BXK_APP_USERNAME",
        "joe",
    )

    monkeypatch.setattr(
        config,
        "BXK_APP_PASSWORD_HASH",
        hash_app_password(
            "OwnerPassword123!"
        ),
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
        "BXK_AUTH_ENABLED",
        False,
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


def add_beta(
    session_factory,
    *,
    active=True,
):
    with session_factory() as session:
        user = User(
            username="beta1",
            email="beta1@example.com",
            password_hash=hash_app_password(
                "BetaPassword123!"
            ),
            role=UserRole.BETA,
            is_active=active,
        )

        session.add(user)
        session.commit()

        return str(user.id)


def test_beta_database_login_and_status(
    monkeypatch,
):
    session_factory = make_session_factory()

    beta_id = add_beta(session_factory)

    configure_auth(
        monkeypatch,
        session_factory,
    )

    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "BetaPassword123!",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] == beta_id
    assert body["username"] == "beta1"
    assert body["role"] == "BETA"
    assert body["auth_source"] == "DATABASE"

    status = client.get(
        "/api/auth/status"
    )

    assert status.status_code == 200

    status_body = status.json()

    assert status_body["authenticated"] is True
    assert status_body["user_id"] == beta_id
    assert status_body["username"] == "beta1"
    assert status_body["role"] == "BETA"
    assert (
        status_body["auth_source"]
        == "DATABASE"
    )


def test_inactive_database_user_cannot_login(
    monkeypatch,
):
    session_factory = make_session_factory()

    add_beta(
        session_factory,
        active=False,
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "username": "beta1",
            "password": "BetaPassword123!",
        },
    )

    assert response.status_code == 401


def test_legacy_owner_login_remains_available(
    monkeypatch,
):
    session_factory = make_session_factory()

    configure_auth(
        monkeypatch,
        session_factory,
    )

    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={
            "username": "joe",
            "password": "OwnerPassword123!",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] is None
    assert body["role"] == "OWNER"
    assert body["auth_source"] == "CONFIG"


def test_database_session_dies_when_user_disabled(
    monkeypatch,
):
    session_factory = make_session_factory()

    beta_id = add_beta(session_factory)

    configure_auth(
        monkeypatch,
        session_factory,
    )

    token = (
        auth_service
        .create_database_session_token(
            beta_id,
            now=1000,
        )
    )

    first = auth_service.verify_session_token(
        token,
        now=1001,
    )

    assert first is not None
    assert first["role"] == "BETA"

    with session_factory() as session:
        user = session.get(
            User,
            __import__("uuid").UUID(beta_id),
        )

        user.is_active = False
        session.commit()

    assert (
        auth_service.verify_session_token(
            token,
            now=1002,
        )
        is None
    )
