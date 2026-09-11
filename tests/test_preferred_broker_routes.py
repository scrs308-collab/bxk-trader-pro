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
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.broker_credential_service import (
    encrypt_broker_secret,
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
):
    with session_factory() as session:
        user = User(
            username="brokerselect",
            email=(
                "brokerselect@example.com"
            ),
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


def add_schwab(
    session_factory,
    user_id,
):
    with session_factory() as session:
        connection = BrokerConnection(
            user_id=uuid.UUID(
                user_id
            ),
            broker="schwab",
            client_secret_encrypted=None,
            refresh_token_encrypted=(
                encrypt_broker_secret(
                    "refresh"
                )
            ),
            access_token_encrypted=(
                encrypt_broker_secret(
                    "access"
                )
            ),
            account_number="11111111",
            base_url=(
                "https://api.schwabapi.com"
            ),
            is_active=True,
            is_verified=True,
            live_trading_enabled=False,
        )

        session.add(connection)
        session.flush()

        session.add(
            BrokerAccount(
                broker_connection_id=(
                    connection.id
                ),
                account_number=(
                    "11111111"
                ),
                broker_account_key=(
                    "HASH111"
                ),
                is_default=True,
                is_active=True,
            )
        )

        session.commit()


def client_for(
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


def test_broker_preferences_require_authentication(
    monkeypatch,
):
    factory = make_session_factory()

    configure_auth(
        monkeypatch,
        factory,
    )

    response = TestClient(
        app
    ).get(
        "/api/broker-connection/brokers"
    )

    assert response.status_code == 401


def test_broker_preferences_default_to_tastytrade(
    monkeypatch,
):
    factory = make_session_factory()

    configure_auth(
        monkeypatch,
        factory,
    )

    user_id = add_user(
        factory
    )

    response = client_for(
        user_id
    ).get(
        "/api/broker-connection/brokers"
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "preferred_broker"
        ]
        == "tastytrade"
    )


def test_select_schwab_route_persists_preference(
    monkeypatch,
):
    factory = make_session_factory()

    configure_auth(
        monkeypatch,
        factory,
    )

    user_id = add_user(
        factory
    )

    add_schwab(
        factory,
        user_id,
    )

    client = client_for(
        user_id
    )

    response = client.post(
        "/api/broker-connection/"
        "brokers/schwab/select"
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "preferred_broker"
        ]
        == "schwab"
    )

    with factory() as session:
        user = session.get(
            User,
            uuid.UUID(
                user_id
            ),
        )

        assert (
            user.preferred_broker
            == "schwab"
        )
