import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

import bxk_app.db_models
from bxk_app import config
from bxk_app.database import (
    Base,
    get_db,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.main import app
from bxk_app.services import (
    auth_service,
    tastytrade_connection_service,
)
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

    Base.metadata.create_all(
        engine
    )

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
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        Fernet.generate_key().decode(),
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

    app.dependency_overrides[
        get_db
    ] = override_get_db


def add_user(
    session_factory,
    *,
    username,
):
    with session_factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=(
                hash_app_password(
                    "Password123!"
                )
            ),
            role=UserRole.BETA,
            is_active=True,
            must_change_password=False,
        )

        session.add(user)
        session.commit()

        return str(
            user.id
        )


def client_with_user(
    user_id,
):
    client = TestClient(
        app
    )

    token = (
        auth_service
        .create_database_session_token(
            user_id
        )
    )

    client.cookies.set(
        auth_service
        .SESSION_COOKIE_NAME,
        token,
    )

    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_tastytrade_connect_requires_authentication(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/tastytrade/connect",
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_tastytrade_connect_redirects_authenticated_user(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    user_id = add_user(
        session_factory,
        username="tastyconnect",
    )

    captured = {}

    def fake_begin(
        session,
        *,
        user_id,
    ):
        captured["user_id"] = (
            user_id
        )

        return {
            "authorization_url":
                "https://auth.example.test/start",
        }

    monkeypatch.setattr(
        tastytrade_connection_service,
        "begin_tastytrade_oauth",
        fake_begin,
    )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/tastytrade/connect",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        response.headers["location"]
        == "https://auth.example.test/start"
    )

    assert (
        str(captured["user_id"])
        == user_id
    )


def test_tastytrade_callback_is_public_and_connects(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    captured = {}

    def fake_complete(
        session,
        *,
        state,
        code,
    ):
        captured["state"] = state
        captured["code"] = code

        return {
            "account_number":
                "5WT07178",
        }

    monkeypatch.setattr(
        tastytrade_connection_service,
        "complete_tastytrade_oauth",
        fake_complete,
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/callback"
        "?state=state-123"
        "&code=code-123",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        response.headers["location"]
        ==
        "/?broker=tastytrade"
        "&status=connected"
    )

    assert captured == {
        "state": "state-123",
        "code": "code-123",
    }


def test_tastytrade_callback_can_require_account_selection(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    def fake_complete(
        session,
        *,
        state,
        code,
    ):
        return {
            "account_number":
                None,
        }

    monkeypatch.setattr(
        tastytrade_connection_service,
        "complete_tastytrade_oauth",
        fake_complete,
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/callback"
        "?state=state-123"
        "&code=code-123",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        response.headers["location"]
        ==
        "/?broker=tastytrade"
        "&status=select-account"
    )


def test_tastytrade_denied_callback_consumes_state(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    captured = {}

    def fake_cancel(
        session,
        *,
        state,
    ):
        captured["state"] = state
        return True

    monkeypatch.setattr(
        tastytrade_connection_service,
        "cancel_tastytrade_oauth",
        fake_cancel,
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/callback"
        "?error=access_denied"
        "&state=state-123",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        response.headers["location"]
        ==
        "/?broker=tastytrade"
        "&status=denied"
    )

    assert (
        captured["state"]
        == "state-123"
    )


def test_tastytrade_callback_requires_state_and_code(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/callback"
        "?state=state-123",
        follow_redirects=False,
    )

    assert response.status_code == 400
