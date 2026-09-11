import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import bxk_app.db_models
from bxk_app.database import Base
from bxk_app.db_models import BrokerConnection


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return engine


def test_broker_connection_has_oauth_fields():
    table = BrokerConnection.__table__

    assert (
        table.c.client_secret_encrypted.nullable
        is True
    )

    assert (
        table.c.refresh_token_encrypted.nullable
        is True
    )

    assert (
        table.c.access_token_encrypted.nullable
        is True
    )

    assert (
        table.c.access_token_expires_at.nullable
        is True
    )

    assert (
        table.c.refresh_token_expires_at.nullable
        is True
    )

    assert (
        table.c.oauth_state_hash.nullable
        is True
    )

    assert (
        table.c.oauth_state_expires_at.nullable
        is True
    )


def test_pending_schwab_connection_needs_no_tokens():
    engine = _make_engine()

    now = datetime.now(
        timezone.utc
    )

    with Session(engine) as session:
        connection = BrokerConnection(
            user_id=uuid.uuid4(),
            broker="schwab",
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            access_token_encrypted=None,
            oauth_state_hash=("a" * 64),
            oauth_state_expires_at=(
                now
                + timedelta(minutes=10)
            ),
            account_number=None,
            base_url=(
                "https://api.schwabapi.com"
            ),
            is_active=True,
            is_verified=False,
            live_trading_enabled=False,
        )

        session.add(connection)
        session.commit()

        assert connection.id is not None
        assert (
            connection.client_secret_encrypted
            is None
        )
        assert (
            connection.refresh_token_encrypted
            is None
        )
        assert (
            connection.access_token_encrypted
            is None
        )
        assert connection.is_verified is False


def test_oauth_state_hash_is_unique():
    engine = _make_engine()

    state_hash = "b" * 64

    with Session(engine) as session:
        first = BrokerConnection(
            user_id=uuid.uuid4(),
            broker="schwab",
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            oauth_state_hash=state_hash,
            account_number=None,
            base_url=(
                "https://api.schwabapi.com"
            ),
            is_active=True,
            is_verified=False,
            live_trading_enabled=False,
        )

        second = BrokerConnection(
            user_id=uuid.uuid4(),
            broker="schwab",
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            oauth_state_hash=state_hash,
            account_number=None,
            base_url=(
                "https://api.schwabapi.com"
            ),
            is_active=True,
            is_verified=False,
            live_trading_enabled=False,
        )

        session.add(first)
        session.commit()

        session.add(second)

        with pytest.raises(
            IntegrityError
        ):
            session.commit()
