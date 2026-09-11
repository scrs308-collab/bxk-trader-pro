import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import bxk_app.db_models
from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.services import (
    broker_connection_service as service,
)
from bxk_app.services.broker_credential_service import (
    encrypt_broker_secret,
)


@pytest.fixture
def db_session(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        Fernet.generate_key().decode(),
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    with Session(engine) as session:
        yield session

    engine.dispose()


def add_user(
    session,
    *,
    role=UserRole.BETA,
):
    user = User(
        id=uuid.uuid4(),
        username=(
            f"user-{uuid.uuid4().hex}"
        ),
        email=(
            f"{uuid.uuid4().hex}@example.com"
        ),
        password_hash="unused",
        role=role,
        is_active=True,
        must_change_password=False,
    )

    session.add(user)
    session.commit()

    return user


def context_for(
    user,
):
    return {
        "user_id":
            str(user.id),
        "role":
            user.role.value,
    }


def add_schwab_connection(
    session,
    *,
    user,
):
    connection = BrokerConnection(
        user_id=user.id,
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
            account_number="11111111",
            broker_account_key="HASH111",
            is_default=True,
            is_active=True,
        )
    )

    session.commit()

    return connection


def test_user_model_has_preferred_broker(
    db_session,
):
    user = add_user(
        db_session
    )

    assert user.preferred_broker is None


def test_existing_user_defaults_to_tastytrade(
    db_session,
):
    user = add_user(
        db_session
    )

    result = (
        service
        .get_user_preferred_broker_name(
            db_session,
            user_context=(
                context_for(user)
            ),
        )
    )

    assert result == "tastytrade"


def test_schwab_can_be_selected_when_ready(
    db_session,
):
    user = add_user(
        db_session
    )

    add_schwab_connection(
        db_session,
        user=user,
    )

    result = (
        service.set_user_preferred_broker(
            db_session,
            user_context=(
                context_for(user)
            ),
            broker_name="SCHWAB",
        )
    )

    db_session.refresh(
        user
    )

    assert (
        user.preferred_broker
        == "schwab"
    )

    assert (
        result["preferred_broker"]
        == "schwab"
    )

    selected = [
        item
        for item
        in result["brokers"]
        if item["selected"]
    ]

    assert len(selected) == 1

    assert (
        selected[0]["broker"]
        == "schwab"
    )


def test_unconfigured_schwab_cannot_be_selected(
    db_session,
):
    user = add_user(
        db_session
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="not ready",
    ):
        service.set_user_preferred_broker(
            db_session,
            user_context=(
                context_for(user)
            ),
            broker_name="schwab",
        )


def test_another_users_schwab_connection_does_not_count(
    db_session,
):
    alpha = add_user(
        db_session
    )

    bravo = add_user(
        db_session
    )

    add_schwab_connection(
        db_session,
        user=bravo,
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="not ready",
    ):
        service.set_user_preferred_broker(
            db_session,
            user_context=(
                context_for(alpha)
            ),
            broker_name="schwab",
        )


def test_unsupported_broker_is_rejected(
    db_session,
):
    user = add_user(
        db_session
    )

    with pytest.raises(
        service.BrokerConnectionInvalid,
        match="not currently supported",
    ):
        service.set_user_preferred_broker(
            db_session,
            user_context=(
                context_for(user)
            ),
            broker_name="ibkr",
        )


def test_resolve_preferred_broker_dispatches_selected_name(
    db_session,
    monkeypatch,
):
    user = add_user(
        db_session
    )

    user.preferred_broker = "schwab"
    db_session.commit()

    expected = object()
    captured = {}

    def fake_resolve(
        session,
        *,
        user_context,
        broker_name,
    ):
        captured[
            "broker_name"
        ] = broker_name

        return expected

    monkeypatch.setattr(
        service,
        "resolve_broker",
        fake_resolve,
    )

    result = (
        service.resolve_preferred_broker(
            db_session,
            user_context=(
                context_for(user)
            ),
        )
    )

    assert result is expected

    assert (
        captured["broker_name"]
        == "schwab"
    )
