import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import (
    Base,
    get_db,
)
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.main import app
from bxk_app.services import (
    auth_service,
    broker_connection_service,
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
    email,
    role=UserRole.BETA,
):
    with session_factory() as session:
        user = User(
            username=username,
            email=email,
            password_hash=(
                hash_app_password(
                    "Password123!"
                )
            ),
            role=role,
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


def fake_accounts(
    **_kwargs,
):
    return [
        {
            "account_number":
                "BETA1234",
            "nickname":
                "Main",
        }
    ]


def test_broker_connection_requires_authentication():
    client = TestClient(
        app
    )

    response = client.get(
        "/api/broker-connection/status"
    )

    assert response.status_code == 401


def test_beta_without_connection_is_disconnected(
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
        username="betaempty",
        email="betaempty@example.com",
    )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/status"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["connected"] is False
    assert payload["source"] == "none"


def test_verify_returns_accounts_without_secrets(
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
        username="betaverify",
        email="betaverify@example.com",
    )

    monkeypatch.setattr(
        broker_connection_service,
        "verify_tastytrade_credentials",
        fake_accounts,
    )

    client = client_with_user(
        user_id
    )

    response = client.post(
        "/api/broker-connection/verify",
        json={
            "client_secret":
                "secret-value",
            "refresh_token":
                "refresh-value",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["verified"] is True

    assert (
        payload["accounts"][0]
        ["account_number"]
        == "BETA1234"
    )

    assert (
        "secret-value"
        not in response.text
    )

    assert (
        "refresh-value"
        not in response.text
    )


def test_connect_stores_encrypted_credentials(
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
        username="betaconnect",
        email="betaconnect@example.com",
    )

    monkeypatch.setattr(
        broker_connection_service,
        "verify_tastytrade_credentials",
        fake_accounts,
    )

    client = client_with_user(
        user_id
    )

    response = client.post(
        "/api/broker-connection/connect",
        json={
            "client_secret":
                "secret-value",
            "refresh_token":
                "refresh-value",
            "account_number":
                "BETA1234",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["connected"] is True
    assert payload["verified"] is True

    assert (
        payload[
            "account_number_masked"
        ]
        == "****1234"
    )

    assert (
        payload[
            "user_live_trading_enabled"
        ]
        is False
    )

    assert (
        "secret-value"
        not in response.text
    )

    assert (
        "refresh-value"
        not in response.text
    )

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            )
        )

        assert connection is not None

        assert str(
            connection.user_id
        ) == user_id

        assert (
            connection
            .client_secret_encrypted
            != "secret-value"
        )

        assert (
            connection
            .refresh_token_encrypted
            != "refresh-value"
        )

        assert (
            connection
            .live_trading_enabled
            is False
        )


def test_other_user_cannot_see_connection(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    alpha_id = add_user(
        session_factory,
        username="alphauser",
        email="alpha@example.com",
    )

    bravo_id = add_user(
        session_factory,
        username="bravouser",
        email="bravo@example.com",
    )

    monkeypatch.setattr(
        broker_connection_service,
        "verify_tastytrade_credentials",
        fake_accounts,
    )

    alpha_client = client_with_user(
        alpha_id
    )

    response = alpha_client.post(
        "/api/broker-connection/connect",
        json={
            "client_secret":
                "alpha-secret",
            "refresh_token":
                "alpha-refresh",
            "account_number":
                "BETA1234",
        },
    )

    assert response.status_code == 200

    bravo_client = client_with_user(
        bravo_id
    )

    response = bravo_client.get(
        "/api/broker-connection/status"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["connected"] is False
    assert payload["source"] == "none"


def test_disconnect_removes_only_current_user_connection(
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
        username="betadelete",
        email="betadelete@example.com",
    )

    monkeypatch.setattr(
        broker_connection_service,
        "verify_tastytrade_credentials",
        fake_accounts,
    )

    client = client_with_user(
        user_id
    )

    response = client.post(
        "/api/broker-connection/connect",
        json={
            "client_secret":
                "secret",
            "refresh_token":
                "refresh",
            "account_number":
                "BETA1234",
        },
    )

    assert response.status_code == 200

    response = client.delete(
        "/api/broker-connection"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["disconnected"]
        is True
    )

    assert (
        payload["status"]
        ["connected"]
        is False
    )

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            )
        )

        assert connection is None


def test_reconnect_resets_live_trading_permission(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    beta_id = add_user(
        session_factory,
        username="beta_reconnect",
        email="beta_reconnect@example.com",
    )

    monkeypatch.setattr(
        broker_connection_service,
        "verify_tastytrade_credentials",
        lambda **kwargs: [
            {
                "account_number":
                    "BETA9999",
                "nickname":
                    "Beta Account",
            }
        ],
    )

    client = client_with_user(
        beta_id
    )

    first = client.post(
        "/api/broker-connection/connect",
        json={
            "client_secret":
                "secret-one",
            "refresh_token":
                "refresh-one",
            "account_number":
                "BETA9999",
        },
    )

    assert first.status_code == 200

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == uuid.UUID(beta_id)
            )
        )

        connection.live_trading_enabled = True

        session.commit()

    second = client.post(
        "/api/broker-connection/connect",
        json={
            "client_secret":
                "secret-two",
            "refresh_token":
                "refresh-two",
            "account_number":
                "BETA9999",
        },
    )

    assert second.status_code == 200

    assert (
        second.json()[
            "user_live_trading_enabled"
        ]
        is False
    )

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == uuid.UUID(beta_id)
            )
        )

        assert (
            connection.live_trading_enabled
            is False
        )

