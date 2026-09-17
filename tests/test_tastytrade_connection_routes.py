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
    role=UserRole.BETA,
    broker_oauth_enabled=False,
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
            role=role,
            broker_oauth_enabled=(
                broker_oauth_enabled
            ),
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


def test_tastytrade_connect_redirects_owner(
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
        role=UserRole.OWNER,
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




def test_tastytrade_connect_rejects_beta_user(
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
        username="tasty-beta-connect",
        role=UserRole.BETA,
    )

    called = {
        "begin": False,
    }

    def fake_begin(
        session,
        *,
        user_id,
    ):
        called["begin"] = True

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
        "/api/broker-connection/"
        "tastytrade/connect",
        follow_redirects=False,
    )

    assert response.status_code == 403

    assert called["begin"] is False


def test_tastytrade_connect_redirects_approved_beta(
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
        username="kdixon",
        role=UserRole.BETA,
        broker_oauth_enabled=True,
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
        tastytrade_connection_service,
        "begin_tastytrade_oauth",
        fake_begin,
    )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/connect",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "https://auth.example.test/start"
    )
    assert str(captured["user_id"]) == user_id

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



def _add_tastytrade_account_connection(
    session_factory,
    *,
    user_id,
    first_number,
    second_number,
):
    from bxk_app.db_models import (
        BrokerAccount,
        BrokerConnection,
    )

    with session_factory() as session:
        connection = BrokerConnection(
            user_id=uuid.UUID(user_id),
            broker="tastytrade",
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            access_token_encrypted=None,
            account_number=None,
            base_url="https://api.tastyworks.com",
            is_active=True,
            is_verified=True,
            live_trading_enabled=False,
        )

        session.add(
            connection
        )
        session.flush()

        first = BrokerAccount(
            broker_connection_id=connection.id,
            account_number=first_number,
            nickname="Primary",
            account_type="Business",
            is_default=False,
            is_active=True,
        )

        second = BrokerAccount(
            broker_connection_id=connection.id,
            account_number=second_number,
            nickname="Secondary",
            account_type="Business",
            is_default=False,
            is_active=True,
        )

        session.add_all([
            first,
            second,
        ])

        session.commit()

        return (
            str(connection.id),
            str(first.id),
            str(second.id),
        )


def test_tastytrade_accounts_route_returns_masked_accounts(
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
        username="tasty-list",
    )

    _add_tastytrade_account_connection(
        session_factory,
        user_id=user_id,
        first_number="1111222233334444",
        second_number="5555666677778888",
    )

    client = client_with_user(
        user_id
    )

    response = client.get(
        "/api/broker-connection/"
        "tastytrade/accounts"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["broker"] == "tastytrade"

    assert len(
        payload["accounts"]
    ) == 2

    assert (
        payload["accounts"][0]
        ["account_number_masked"]
        == "************4444"
    )

    assert (
        payload["accounts"][1]
        ["account_number_masked"]
        == "************8888"
    )

    assert (
        "1111222233334444"
        not in response.text
    )

    assert (
        "5555666677778888"
        not in response.text
    )


def test_tastytrade_account_select_route_updates_selection(
    monkeypatch,
):
    from sqlalchemy import select

    from bxk_app.db_models import (
        BrokerAccount,
        BrokerConnection,
    )

    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    user_id = add_user(
        session_factory,
        username="tasty-select",
    )

    (
        _connection_id,
        first_id,
        second_id,
    ) = _add_tastytrade_account_connection(
        session_factory,
        user_id=user_id,
        first_number="TT1111",
        second_number="TT2222",
    )

    client = client_with_user(
        user_id
    )

    response = client.post(
        (
            "/api/broker-connection/"
            f"tastytrade/accounts/"
            f"{second_id}/select"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["broker"] == "tastytrade"
    assert payload["selected"] is True

    assert (
        payload["account"]
        ["account_number_masked"]
        == "**2222"
    )

    with session_factory() as session:
        connection = session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == uuid.UUID(user_id),
                BrokerConnection.broker
                == "tastytrade",
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

        first = next(
            account
            for account in accounts
            if str(account.id)
            == first_id
        )

        second = next(
            account
            for account in accounts
            if str(account.id)
            == second_id
        )

        assert (
            connection.account_number
            == "TT2222"
        )

        assert first.is_default is False
        assert second.is_default is True


def test_tastytrade_account_select_rejects_other_user(
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
        username="tasty-alpha",
    )

    bravo_id = add_user(
        session_factory,
        username="tasty-bravo",
    )

    _add_tastytrade_account_connection(
        session_factory,
        user_id=alpha_id,
        first_number="ALPHA1111",
        second_number="ALPHA2222",
    )

    (
        _bravo_connection_id,
        bravo_account_id,
        _bravo_second_id,
    ) = _add_tastytrade_account_connection(
        session_factory,
        user_id=bravo_id,
        first_number="BRAVO3333",
        second_number="BRAVO4444",
    )

    alpha_client = client_with_user(
        alpha_id
    )

    response = alpha_client.post(
        (
            "/api/broker-connection/"
            f"tastytrade/accounts/"
            f"{bravo_account_id}/select"
        )
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Tastytrade account not found."
    )

    assert (
        "BRAVO3333"
        not in response.text
    )
