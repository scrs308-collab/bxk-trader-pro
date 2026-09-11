import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import bxk_app.db_models
from bxk_app.database import Base
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return engine


def _make_connection(session):
    connection = BrokerConnection(
        user_id=uuid.uuid4(),
        broker="schwab",
        client_secret_encrypted="placeholder",
        refresh_token_encrypted="placeholder",
        account_number=None,
        base_url=(
            "https://api.schwabapi.com"
        ),
        is_active=True,
        is_verified=False,
        live_trading_enabled=False,
    )

    session.add(connection)
    session.flush()

    return connection


def test_broker_account_model_is_registered():
    assert (
        "broker_accounts"
        in Base.metadata.tables
    )

    assert (
        bxk_app.db_models.BrokerAccount
        is BrokerAccount
    )


def test_connection_can_have_multiple_broker_accounts():
    engine = _make_engine()

    with Session(engine) as session:
        connection = _make_connection(
            session
        )

        first = BrokerAccount(
            broker_connection_id=connection.id,
            account_number="11111111",
            broker_account_key="hash-one",
            nickname="Primary",
            account_type="MARGIN",
            is_default=True,
        )

        second = BrokerAccount(
            broker_connection_id=connection.id,
            account_number="22222222",
            broker_account_key="hash-two",
            nickname="Secondary",
            account_type="CASH",
            is_default=False,
        )

        session.add_all(
            [first, second]
        )

        session.commit()

        accounts = (
            session.query(BrokerAccount)
            .filter(
                BrokerAccount.broker_connection_id
                == connection.id
            )
            .all()
        )

        assert len(accounts) == 2

        default_accounts = [
            account
            for account in accounts
            if account.is_default
        ]

        assert len(default_accounts) == 1
        assert (
            default_accounts[0].account_number
            == "11111111"
        )


def test_duplicate_account_is_rejected_per_connection():
    engine = _make_engine()

    with Session(engine) as session:
        connection = _make_connection(
            session
        )

        session.add(
            BrokerAccount(
                broker_connection_id=connection.id,
                account_number="11111111",
            )
        )

        session.commit()

        session.add(
            BrokerAccount(
                broker_connection_id=connection.id,
                account_number="11111111",
            )
        )

        with pytest.raises(
            IntegrityError
        ):
            session.commit()
