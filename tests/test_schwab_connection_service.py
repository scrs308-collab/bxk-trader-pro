import hashlib
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)
from bxk_app.services import (
    schwab_connection_service
    as service,
)
from bxk_app.services import (
    schwab_oauth_service,
)
from bxk_app.services.broker_credential_service import (
    decrypt_broker_secret,
)


NOW = datetime(
    2026,
    9,
    11,
    19,
    0,
    tzinfo=timezone.utc,
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


def _begin(
    session,
    user_id,
    *,
    state="raw-state-123",
    now=NOW,
):
    return service.begin_schwab_oauth(
        session,
        user_id=user_id,
        now=now,
        state_factory=(
            lambda: state
        ),
        authorization_url_builder=(
            lambda value:
                (
                    "https://auth.test/"
                    f"?state={value}"
                )
        ),
    )


def _token_exchange(
    code,
):
    assert code == "code-123"

    return {
        "access_token":
            "access-token-123",
        "refresh_token":
            "refresh-token-123",
        "expires_in":
            1800,
    }


def _broker_factory(
    accounts,
):
    class FakeBroker:
        last_error = None

        def __init__(
            self,
            *,
            access_token,
            account_number=None,
        ):
            assert (
                access_token
                == "access-token-123"
            )

            assert (
                account_number
                is None
            )

        def get_accounts(
            self,
            force=False,
        ):
            assert force is True
            return accounts

    return FakeBroker


def test_begin_oauth_creates_pending_connection(
    db_session,
):
    user_id = uuid.uuid4()

    result = _begin(
        db_session,
        user_id,
    )

    connection = (
        db_session.scalar(
            select(
                BrokerConnection
            ).where(
                BrokerConnection.user_id
                == user_id,
                BrokerConnection.broker
                == "schwab",
            )
        )
    )

    assert connection is not None

    expected_hash = hashlib.sha256(
        b"raw-state-123"
    ).hexdigest()

    assert (
        connection.oauth_state_hash
        == expected_hash
    )

    assert (
        connection.oauth_state_hash
        != "raw-state-123"
    )

    assert (
        connection.oauth_state_expires_at
        is not None
    )

    assert connection.is_verified is False

    assert (
        result["authorization_url"]
        == (
            "https://auth.test/"
            "?state=raw-state-123"
        )
    )


def test_begin_oauth_reuses_existing_connection(
    db_session,
):
    user_id = uuid.uuid4()

    existing = BrokerConnection(
        user_id=user_id,
        broker="schwab",
        client_secret_encrypted=None,
        refresh_token_encrypted=(
            "existing-refresh"
        ),
        access_token_encrypted=(
            "existing-access"
        ),
        account_number="11111111",
        base_url=(
            "https://api.schwabapi.com"
        ),
        is_active=True,
        is_verified=True,
        live_trading_enabled=False,
    )

    db_session.add(existing)
    db_session.commit()

    existing_id = existing.id

    _begin(
        db_session,
        user_id,
        state="new-state",
    )

    connection = (
        service.get_schwab_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert connection.id == existing_id
    assert connection.is_verified is True

    assert (
        connection.access_token_encrypted
        == "existing-access"
    )

    assert (
        connection.refresh_token_encrypted
        == "existing-refresh"
    )

    assert (
        connection.oauth_state_hash
        == hashlib.sha256(
            b"new-state"
        ).hexdigest()
    )


def test_complete_oauth_encrypts_tokens_and_syncs_account(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    result = service.complete_schwab_oauth(
        db_session,
        state="raw-state-123",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                {
                    "account_number":
                        "11111111",
                    "broker_account_key":
                        "HASH111",
                }
            ])
        ),
    )

    connection = (
        service.get_schwab_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert connection.is_verified is True

    assert (
        connection.account_number
        == "11111111"
    )

    assert (
        connection.oauth_state_hash
        is None
    )

    assert (
        connection.oauth_state_expires_at
        is None
    )

    assert (
        decrypt_broker_secret(
            connection
            .access_token_encrypted
        )
        == "access-token-123"
    )

    assert (
        decrypt_broker_secret(
            connection
            .refresh_token_encrypted
        )
        == "refresh-token-123"
    )

    access_expiry = (
        service._normalize_datetime(
            connection
            .access_token_expires_at
        )
    )

    refresh_expiry = (
        service._normalize_datetime(
            connection
            .refresh_token_expires_at
        )
    )

    assert access_expiry == (
        NOW
        + timedelta(
            seconds=1800
        )
    )

    assert refresh_expiry == (
        NOW
        + timedelta(days=7)
    )

    accounts = list(
        db_session.scalars(
            select(
                BrokerAccount
            ).where(
                BrokerAccount
                .broker_connection_id
                == connection.id
            )
        ).all()
    )

    assert len(accounts) == 1

    assert accounts[0].is_default is True

    assert (
        accounts[0].broker_account_key
        == "HASH111"
    )

    assert result["connected"] is True

    with pytest.raises(
        service.SchwabOAuthStateInvalid,
        match="already been used",
    ):
        service.complete_schwab_oauth(
            db_session,
            state="raw-state-123",
            code="code-123",
            now=NOW,
            token_exchange=(
                _token_exchange
            ),
            broker_factory=(
                _broker_factory([])
            ),
        )


def test_multiple_accounts_require_later_selection(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    service.complete_schwab_oauth(
        db_session,
        state="raw-state-123",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                {
                    "account_number":
                        "11111111",
                    "broker_account_key":
                        "HASH111",
                },
                {
                    "account_number":
                        "22222222",
                    "broker_account_key":
                        "HASH222",
                },
            ])
        ),
    )

    connection = (
        service.get_schwab_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert (
        connection.account_number
        is None
    )

    accounts = list(
        db_session.scalars(
            select(
                BrokerAccount
            ).where(
                BrokerAccount
                .broker_connection_id
                == connection.id
            )
        ).all()
    )

    assert len(accounts) == 2

    assert not any(
        account.is_default
        for account in accounts
    )


def test_expired_state_is_rejected_and_consumed(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
        now=NOW,
    )

    with pytest.raises(
        service.SchwabOAuthStateInvalid,
        match="expired",
    ):
        service.complete_schwab_oauth(
            db_session,
            state="raw-state-123",
            code="code-123",
            now=(
                NOW
                + timedelta(
                    minutes=11
                )
            ),
            token_exchange=(
                _token_exchange
            ),
        )

    connection = (
        service.get_schwab_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert (
        connection.oauth_state_hash
        is None
    )

    assert (
        connection.oauth_state_expires_at
        is None
    )


def test_failed_token_exchange_still_consumes_state(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    def fail_exchange(code):
        raise (
            schwab_oauth_service
            .SchwabOAuthError(
                "bad code"
            )
        )

    with pytest.raises(
        service.SchwabConnectionError,
        match="token exchange failed",
    ):
        service.complete_schwab_oauth(
            db_session,
            state="raw-state-123",
            code="bad-code",
            now=NOW,
            token_exchange=(
                fail_exchange
            ),
        )

    connection = (
        service.get_schwab_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert (
        connection.oauth_state_hash
        is None
    )

    assert (
        connection.access_token_encrypted
        is None
    )

    assert connection.is_verified is False


def test_reauthorization_preserves_default_and_deactivates_removed_accounts(
    db_session,
):
    user_id = uuid.uuid4()

    connection = BrokerConnection(
        user_id=user_id,
        broker="schwab",
        client_secret_encrypted=None,
        refresh_token_encrypted=(
            "old-refresh"
        ),
        access_token_encrypted=(
            "old-access"
        ),
        account_number="11111111",
        base_url=(
            "https://api.schwabapi.com"
        ),
        is_active=True,
        is_verified=True,
        live_trading_enabled=False,
    )

    db_session.add(connection)
    db_session.flush()

    db_session.add_all([
        BrokerAccount(
            broker_connection_id=(
                connection.id
            ),
            account_number="11111111",
            broker_account_key="OLDHASH111",
            is_default=True,
            is_active=True,
        ),
        BrokerAccount(
            broker_connection_id=(
                connection.id
            ),
            account_number="22222222",
            broker_account_key="OLDHASH222",
            is_default=False,
            is_active=True,
        ),
    ])

    db_session.commit()

    _begin(
        db_session,
        user_id,
        state="reauth-state",
    )

    service.complete_schwab_oauth(
        db_session,
        state="reauth-state",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                {
                    "account_number":
                        "11111111",
                    "broker_account_key":
                        "NEWHASH111",
                },
                {
                    "account_number":
                        "33333333",
                    "broker_account_key":
                        "HASH333",
                },
            ])
        ),
    )

    rows = list(
        db_session.scalars(
            select(
                BrokerAccount
            ).where(
                BrokerAccount
                .broker_connection_id
                == connection.id
            )
        ).all()
    )

    by_number = {
        row.account_number:
            row
        for row in rows
    }

    assert (
        connection.account_number
        == "11111111"
    )

    assert (
        by_number[
            "11111111"
        ].is_default
        is True
    )

    assert (
        by_number[
            "11111111"
        ].broker_account_key
        == "NEWHASH111"
    )

    assert (
        by_number[
            "22222222"
        ].is_active
        is False
    )

    assert (
        by_number[
            "22222222"
        ].is_default
        is False
    )

    assert (
        by_number[
            "33333333"
        ].is_active
        is True
    )
