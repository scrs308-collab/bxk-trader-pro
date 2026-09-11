import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import bxk_app.db_models
from bxk_app import config
from bxk_app.brokers.schwab import SchwabBroker
from bxk_app.database import Base
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)
from bxk_app.services import (
    broker_connection_service as service,
)
from bxk_app.services import (
    schwab_oauth_service,
)
from bxk_app.services.broker_credential_service import (
    decrypt_broker_secret,
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


def context_for(
    user_id,
):
    return {
        "user_id":
            str(user_id),
        "role":
            "BETA",
    }


def add_connection(
    session,
    *,
    user_id,
    verified=True,
    account_number="11111111",
    access_expires_at=None,
    refresh_expires_at=None,
):
    now = datetime.now(
        timezone.utc
    )

    connection = BrokerConnection(
        user_id=user_id,
        broker="schwab",
        client_secret_encrypted=None,
        refresh_token_encrypted=(
            encrypt_broker_secret(
                "refresh-old"
            )
        ),
        access_token_encrypted=(
            encrypt_broker_secret(
                "access-old"
            )
        ),
        access_token_expires_at=(
            access_expires_at
            or (
                now
                + timedelta(
                    minutes=20
                )
            )
        ),
        refresh_token_expires_at=(
            refresh_expires_at
            or (
                now
                + timedelta(
                    days=3
                )
            )
        ),
        account_number=account_number,
        base_url=(
            "https://api.schwabapi.com"
        ),
        is_active=True,
        is_verified=verified,
        live_trading_enabled=False,
    )

    session.add(
        connection
    )

    session.flush()

    if account_number:
        session.add(
            BrokerAccount(
                broker_connection_id=(
                    connection.id
                ),
                account_number=(
                    account_number
                ),
                broker_account_key=(
                    "HASH111"
                ),
                is_default=True,
                is_active=True,
            )
        )

    session.commit()

    return connection


def test_resolve_schwab_uses_stored_access_token(
    db_session,
):
    user_id = uuid.uuid4()

    add_connection(
        db_session,
        user_id=user_id,
    )

    broker = (
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    user_id
                )
            ),
        )
    )

    assert isinstance(
        broker,
        SchwabBroker,
    )

    assert (
        broker.access_token
        == "access-old"
    )

    assert (
        broker.account_number
        == "11111111"
    )

    assert (
        broker.base_url
        == "https://api.schwabapi.com"
    )


def test_resolve_schwab_requires_connection(
    db_session,
):
    with pytest.raises(
        service.BrokerConnectionRequired,
        match="No Schwab account",
    ):
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    uuid.uuid4()
                )
            ),
        )


def test_resolve_schwab_requires_verified_connection(
    db_session,
):
    user_id = uuid.uuid4()

    add_connection(
        db_session,
        user_id=user_id,
        verified=False,
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="not been verified",
    ):
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    user_id
                )
            ),
        )


def test_resolve_schwab_requires_selected_account(
    db_session,
):
    user_id = uuid.uuid4()

    add_connection(
        db_session,
        user_id=user_id,
        account_number=None,
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="Select a Schwab account",
    ):
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    user_id
                )
            ),
        )


def test_resolve_schwab_refreshes_expiring_access_token(
    db_session,
    monkeypatch,
):
    user_id = uuid.uuid4()

    now = datetime.now(
        timezone.utc
    )

    connection = add_connection(
        db_session,
        user_id=user_id,
        access_expires_at=(
            now
            + timedelta(
                seconds=30
            )
        ),
        refresh_expires_at=(
            now
            + timedelta(
                days=3
            )
        ),
    )

    captured = {}

    def fake_refresh(
        refresh_token,
    ):
        captured[
            "refresh_token"
        ] = refresh_token

        return {
            "access_token":
                "access-new",
            "refresh_token":
                "refresh-rotated",
            "expires_in":
                1800,
        }

    monkeypatch.setattr(
        schwab_oauth_service,
        "refresh_access_token",
        fake_refresh,
    )

    broker = (
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    user_id
                )
            ),
        )
    )

    assert (
        captured[
            "refresh_token"
        ]
        == "refresh-old"
    )

    assert (
        broker.access_token
        == "access-new"
    )

    db_session.refresh(
        connection
    )

    assert (
        decrypt_broker_secret(
            connection
            .access_token_encrypted
        )
        == "access-new"
    )

    assert (
        decrypt_broker_secret(
            connection
            .refresh_token_encrypted
        )
        == "refresh-rotated"
    )

    assert (
        connection
        .access_token_expires_at
        is not None
    )


def test_resolve_schwab_rejects_expired_authorization(
    db_session,
    monkeypatch,
):
    user_id = uuid.uuid4()

    now = datetime.now(
        timezone.utc
    )

    add_connection(
        db_session,
        user_id=user_id,
        access_expires_at=(
            now
            - timedelta(
                minutes=1
            )
        ),
        refresh_expires_at=(
            now
            - timedelta(
                seconds=1
            )
        ),
    )

    called = {
        "value": False,
    }

    def should_not_refresh(
        refresh_token,
    ):
        called["value"] = True

        raise AssertionError(
            "Refresh should not be attempted."
        )

    monkeypatch.setattr(
        schwab_oauth_service,
        "refresh_access_token",
        should_not_refresh,
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="authorization has expired",
    ):
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    user_id
                )
            ),
        )

    assert (
        called["value"]
        is False
    )


def test_resolve_schwab_never_uses_another_users_connection(
    db_session,
):
    owner_id = uuid.uuid4()
    requesting_user_id = uuid.uuid4()

    add_connection(
        db_session,
        user_id=owner_id,
    )

    with pytest.raises(
        service.BrokerConnectionRequired,
        match="No Schwab account",
    ):
        service.resolve_schwab_broker(
            db_session,
            user_context=(
                context_for(
                    requesting_user_id
                )
            ),
        )
