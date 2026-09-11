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
from bxk_app.services import (
    auth_service,
    schwab_connection_service,
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
            email=(
                f"{username}@example.com"
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


def test_schwab_connect_requires_authentication(
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
        "/api/broker-connection/schwab/connect",
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_schwab_connect_redirects_authenticated_user(
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
        username="schwabconnect",
    )

    captured = {}

    def fake_begin(
        session,
        *,
        user_id,
    ):
        captured["user_id"] = user_id

        return {
            "authorization_url":
                "https://auth.example.test/start",
        }

    monkeypatch.setattr(
        schwab_connection_service,
        "begin_schwab_oauth",
        fake_begin,
    )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/schwab/connect",
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


def test_schwab_callback_is_public_with_auth_enabled(
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
        assert state == "state-123"
        assert code == "code-123"

        return {
            "connected": True,
            "account_number":
                "11111111",
        }

    monkeypatch.setattr(
        schwab_connection_service,
        "complete_schwab_oauth",
        fake_complete,
    )

    client = TestClient(
        app
    )

    response = client.get(
        (
            "/api/broker-connection/"
            "schwab/callback"
            "?state=state-123"
            "&code=code-123"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert (
        response.headers["location"]
        == (
            "/?broker=schwab"
            "&status=connected"
        )
    )


def test_schwab_callback_rejects_invalid_state(
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
        raise (
            schwab_connection_service
            .SchwabOAuthStateInvalid(
                "Invalid OAuth state."
            )
        )

    monkeypatch.setattr(
        schwab_connection_service,
        "complete_schwab_oauth",
        fake_complete,
    )

    client = TestClient(
        app
    )

    response = client.get(
        (
            "/api/broker-connection/"
            "schwab/callback"
            "?state=bad-state"
            "&code=bad-code"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_schwab_accounts_are_masked_and_selectable(
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
        username="schwabaccounts",
    )

    with session_factory() as session:
        connection = BrokerConnection(
            user_id=uuid.UUID(
                user_id
            ),
            broker="schwab",
            client_secret_encrypted=None,
            refresh_token_encrypted=(
                "encrypted-refresh"
            ),
            access_token_encrypted=(
                "encrypted-access"
            ),
            account_number=None,
            base_url=(
                "https://api.schwabapi.com"
            ),
            is_active=True,
            is_verified=True,
            live_trading_enabled=False,
        )

        session.add(connection)
        session.flush()

        first = BrokerAccount(
            broker_connection_id=(
                connection.id
            ),
            account_number=(
                "1111222233334444"
            ),
            broker_account_key="HASH1",
            is_default=False,
            is_active=True,
        )

        second = BrokerAccount(
            broker_connection_id=(
                connection.id
            ),
            account_number=(
                "5555666677778888"
            ),
            broker_account_key="HASH2",
            is_default=False,
            is_active=True,
        )

        session.add_all([
            first,
            second,
        ])

        session.commit()

        selected_id = str(
            second.id
        )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/schwab/accounts"
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(
        payload["accounts"]
    ) == 2

    assert (
        "1111222233334444"
        not in response.text
    )

    assert (
        "5555666677778888"
        not in response.text
    )

    masked = {
        item[
            "account_number_masked"
        ]
        for item
        in payload["accounts"]
    }

    assert (
        "************4444"
        in masked
    )

    assert (
        "************8888"
        in masked
    )

    response = client.post(
        (
            "/api/broker-connection/"
            f"schwab/accounts/"
            f"{selected_id}/select"
        )
    )

    assert response.status_code == 200

    assert (
        response.json()["selected"]
        is True
    )

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == uuid.UUID(
                    user_id
                ),
                BrokerConnection.broker
                == "schwab",
            )
        )

        accounts = list(
            session.scalars(
                select(
                    BrokerAccount
                ).where(
                    BrokerAccount
                    .broker_connection_id
                    == connection.id
                )
            ).all()
        )

        selected = [
            account
            for account in accounts
            if account.is_default
        ]

        assert len(
            selected
        ) == 1

        assert (
            str(selected[0].id)
            == selected_id
        )

        assert (
            connection.account_number
            == "5555666677778888"
        )


def test_user_cannot_select_another_users_schwab_account(
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
        username="schwabalpha",
    )

    bravo_id = add_user(
        session_factory,
        username="schwabbravo",
    )

    with session_factory() as session:
        bravo_connection = (
            BrokerConnection(
                user_id=uuid.UUID(
                    bravo_id
                ),
                broker="schwab",
                client_secret_encrypted=None,
                refresh_token_encrypted=(
                    "encrypted-refresh"
                ),
                access_token_encrypted=(
                    "encrypted-access"
                ),
                account_number=None,
                base_url=(
                    "https://api.schwabapi.com"
                ),
                is_active=True,
                is_verified=True,
                live_trading_enabled=False,
            )
        )

        session.add(
            bravo_connection
        )

        session.flush()

        bravo_account = (
            BrokerAccount(
                broker_connection_id=(
                    bravo_connection.id
                ),
                account_number=(
                    "9999000011112222"
                ),
                broker_account_key=(
                    "BRAVOHASH"
                ),
                is_default=True,
                is_active=True,
            )
        )

        session.add(
            bravo_account
        )

        session.commit()

        bravo_account_id = str(
            bravo_account.id
        )

    alpha_client = (
        client_with_user(
            alpha_id
        )
    )

    response = alpha_client.post(
        (
            "/api/broker-connection/"
            f"schwab/accounts/"
            f"{bravo_account_id}/select"
        )
    )

    assert response.status_code == 404

    assert (
        "9999000011112222"
        not in response.text
    )
