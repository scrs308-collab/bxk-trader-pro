import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
    broker as owner_broker,
)
from bxk_app.database import Base
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    resolve_tastytrade_broker,
)
from bxk_app.services.broker_credential_service import (
    encrypt_broker_secret,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            BrokerConnection.__table__,
        ],
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def credential_key(
    monkeypatch,
):
    key = Fernet.generate_key().decode()

    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        key,
    )

    return key


def make_user(
    session,
    *,
    username,
    role,
):
    user = User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        password_hash="not-used-in-test",
        role=role,
        is_active=True,
    )

    session.add(user)
    session.commit()

    return user


def add_connection(
    session,
    *,
    user,
    client_secret,
    refresh_token,
    account_number,
    verified=True,
    live_trading_enabled=False,
):
    connection = BrokerConnection(
        user_id=user.id,
        broker="tastytrade",
        client_secret_encrypted=(
            encrypt_broker_secret(
                client_secret
            )
        ),
        refresh_token_encrypted=(
            encrypt_broker_secret(
                refresh_token
            )
        ),
        account_number=account_number,
        base_url="https://api.tastyworks.com",
        is_active=True,
        is_verified=verified,
        live_trading_enabled=(
            live_trading_enabled
        ),
    )

    session.add(connection)
    session.commit()

    return connection


def context_for(user):
    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value,
    }


def test_owner_without_connection_uses_legacy_owner_broker(
    db_session,
):
    owner = make_user(
        db_session,
        username="owner",
        role=UserRole.OWNER,
    )

    resolved = resolve_tastytrade_broker(
        db_session,
        user_context=context_for(owner),
    )

    assert resolved is owner_broker


def test_beta_without_connection_never_gets_owner_broker(
    db_session,
):
    beta = make_user(
        db_session,
        username="beta",
        role=UserRole.BETA,
    )

    with pytest.raises(
        BrokerConnectionRequired
    ):
        resolve_tastytrade_broker(
            db_session,
            user_context=context_for(beta),
        )


def test_beta_resolves_only_own_credentials(
    db_session,
    credential_key,
):
    alpha = make_user(
        db_session,
        username="alpha",
        role=UserRole.BETA,
    )

    bravo = make_user(
        db_session,
        username="bravo",
        role=UserRole.BETA,
    )

    add_connection(
        db_session,
        user=alpha,
        client_secret="alpha-secret",
        refresh_token="alpha-refresh",
        account_number="ALPHA123",
    )

    add_connection(
        db_session,
        user=bravo,
        client_secret="bravo-secret",
        refresh_token="bravo-refresh",
        account_number="BRAVO456",
    )

    alpha_broker = resolve_tastytrade_broker(
        db_session,
        user_context=context_for(alpha),
    )

    bravo_broker = resolve_tastytrade_broker(
        db_session,
        user_context=context_for(bravo),
    )

    assert isinstance(
        alpha_broker,
        TastytradeBroker,
    )

    assert isinstance(
        bravo_broker,
        TastytradeBroker,
    )

    assert alpha_broker is not owner_broker
    assert bravo_broker is not owner_broker

    assert (
        alpha_broker.client_secret
        == "alpha-secret"
    )

    assert (
        alpha_broker.refresh_token
        == "alpha-refresh"
    )

    assert (
        alpha_broker.account_number
        == "ALPHA123"
    )

    assert (
        bravo_broker.client_secret
        == "bravo-secret"
    )

    assert (
        bravo_broker.refresh_token
        == "bravo-refresh"
    )

    assert (
        bravo_broker.account_number
        == "BRAVO456"
    )

    assert (
        alpha_broker.client_secret
        != bravo_broker.client_secret
    )


def test_unverified_beta_connection_fails_closed(
    db_session,
    credential_key,
):
    beta = make_user(
        db_session,
        username="unverified",
        role=UserRole.BETA,
    )

    add_connection(
        db_session,
        user=beta,
        client_secret="secret",
        refresh_token="refresh",
        account_number="TEST123",
        verified=False,
    )

    with pytest.raises(
        BrokerConnectionRequired
    ):
        resolve_tastytrade_broker(
            db_session,
            user_context=context_for(beta),
        )


def test_bad_owner_connection_does_not_fall_back_to_global_broker(
    db_session,
    credential_key,
):
    owner = make_user(
        db_session,
        username="ownerbad",
        role=UserRole.OWNER,
    )

    connection = BrokerConnection(
        user_id=owner.id,
        broker="tastytrade",
        client_secret_encrypted=(
            "not-valid-ciphertext"
        ),
        refresh_token_encrypted=(
            "also-invalid"
        ),
        account_number="OWNER123",
        base_url="https://api.tastyworks.com",
        is_active=True,
        is_verified=True,
        live_trading_enabled=True,
    )

    db_session.add(connection)
    db_session.commit()

    with pytest.raises(
        BrokerConnectionInvalid
    ):
        resolve_tastytrade_broker(
            db_session,
            user_context=context_for(owner),
        )


def test_user_live_trading_defaults_to_disabled(
    db_session,
    credential_key,
):
    beta = make_user(
        db_session,
        username="safebeta",
        role=UserRole.BETA,
    )

    add_connection(
        db_session,
        user=beta,
        client_secret="secret",
        refresh_token="refresh",
        account_number="SAFE123",
        live_trading_enabled=False,
    )

    resolved = resolve_tastytrade_broker(
        db_session,
        user_context=context_for(beta),
    )

    assert (
        resolved.live_trading_enabled
        is False
    )
