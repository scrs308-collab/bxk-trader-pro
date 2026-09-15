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
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

import bxk_app.db_models
from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models import (
    BrokerAccount,
    BrokerConnection,
)
from bxk_app.services import (
    tastytrade_connection_service as service,
)
from bxk_app.services import (
    tastytrade_oauth_service,
)
from bxk_app.services.broker_credential_service import (
    decrypt_broker_secret,
)


NOW = datetime(
    2026,
    9,
    15,
    18,
    30,
    tzinfo=timezone.utc,
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


@pytest.fixture
def db_session(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        Fernet.generate_key().decode(),
    )

    monkeypatch.setattr(
        config,
        "TASTYTRADE_CLIENT_SECRET",
        "bxk-application-secret",
    )

    monkeypatch.setattr(
        config,
        "TASTYTRADE_BASE_URL",
        "https://api.tastyworks.com",
    )

    factory = make_session_factory()

    with factory() as session:
        yield session


def _begin(
    session,
    user_id,
    *,
    state="raw-state-123",
    now=NOW,
):
    return service.begin_tastytrade_oauth(
        session,
        user_id=user_id,
        now=now,
        state_factory=lambda: state,
        authorization_url_builder=(
            lambda raw_state:
                "https://auth.example.test/start"
                f"?state={raw_state}"
        ),
    )


def _token_exchange(
    code,
):
    assert code == "code-123"

    return {
        "access_token":
            "access-123",
        "refresh_token":
            "refresh-123",
        "expires_in":
            900,
        "token_type":
            "Bearer",
        "scope":
            "read trade openid",
        "id_token":
            "id-123",
    }


class FakeBroker:
    def __init__(
        self,
        accounts,
    ):
        self.accounts = accounts
        self.last_error = None

    def get_accounts(self):
        return self.accounts


def _broker_factory(
    accounts,
    captured=None,
):
    def factory(**kwargs):
        if captured is not None:
            captured.update(
                kwargs
            )

        return FakeBroker(
            accounts
        )

    return factory


def _raw_account(
    number,
    *,
    nickname="",
    account_type="Business",
):
    return {
        "authority-level":
            "owner",
        "account": {
            "account-number":
                number,
            "nickname":
                nickname,
            "account-type-name":
                account_type,
        },
    }


def _utc_value(
    value,
):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def test_begin_oauth_hashes_state_and_binds_user(
    db_session,
):
    user_id = uuid.uuid4()

    result = _begin(
        db_session,
        user_id,
    )

    connection = (
        service.get_tastytrade_connection(
            db_session,
            user_id=user_id,
        )
    )

    expected_hash = hashlib.sha256(
        b"raw-state-123"
    ).hexdigest()

    assert connection is not None

    assert (
        connection.user_id
        == user_id
    )

    assert (
        connection.broker
        == "tastytrade"
    )

    assert (
        connection.oauth_state_hash
        == expected_hash
    )

    assert (
        connection.oauth_state_hash
        != "raw-state-123"
    )

    assert (
        _utc_value(
            connection
            .oauth_state_expires_at
        )
        == NOW
        + timedelta(minutes=10)
    )

    assert (
        connection.client_secret_encrypted
        is None
    )

    assert (
        connection.is_verified
        is False
    )

    assert result["broker"] == "tastytrade"

    assert (
        result["authorization_url"]
        ==
        "https://auth.example.test/start"
        "?state=raw-state-123"
    )


def test_complete_oauth_stores_tokens_and_single_account(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    captured = {}

    result = service.complete_tastytrade_oauth(
        db_session,
        state="raw-state-123",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory(
                [
                    _raw_account(
                        "5WT07178",
                        nickname="BXK",
                    ),
                ],
                captured=captured,
            )
        ),
    )

    connection = (
        service.get_tastytrade_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert connection is not None

    assert (
        decrypt_broker_secret(
            connection
            .access_token_encrypted
        )
        == "access-123"
    )

    assert (
        decrypt_broker_secret(
            connection
            .refresh_token_encrypted
        )
        == "refresh-123"
    )

    # The application secret belongs to BXK,
    # not to an individual user's connection.
    assert (
        connection.client_secret_encrypted
        is None
    )

    assert (
        _utc_value(
            connection
            .access_token_expires_at
        )
        == NOW
        + timedelta(seconds=900)
    )

    # Tastytrade refresh tokens do not expire.
    assert (
        connection.refresh_token_expires_at
        is None
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
        connection.account_number
        == "5WT07178"
    )

    assert connection.is_active is True
    assert connection.is_verified is True

    assert (
        _utc_value(
            connection.last_verified_at
        )
        == NOW
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

    assert (
        accounts[0].account_number
        == "5WT07178"
    )

    assert (
        accounts[0].nickname
        == "BXK"
    )

    assert (
        accounts[0].account_type
        == "Business"
    )

    assert accounts[0].is_active is True
    assert accounts[0].is_default is True

    assert (
        captured["access_token"]
        == "access-123"
    )

    assert (
        captured["refresh_token"]
        == "refresh-123"
    )

    assert result["connected"] is True
    assert result["verified"] is True

    assert (
        result["account_number"]
        == "5WT07178"
    )


def test_multiple_accounts_require_selection(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    result = service.complete_tastytrade_oauth(
        db_session,
        state="raw-state-123",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                _raw_account(
                    "11111111"
                ),
                _raw_account(
                    "22222222"
                ),
            ])
        ),
    )

    connection = (
        service.get_tastytrade_connection(
            db_session,
            user_id=user_id,
        )
    )

    assert connection is not None

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

    assert (
        result["account_number"]
        is None
    )


def test_oauth_state_cannot_be_replayed(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    service.complete_tastytrade_oauth(
        db_session,
        state="raw-state-123",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                _raw_account(
                    "11111111"
                ),
            ])
        ),
    )

    with pytest.raises(
        service.TastytradeOAuthStateInvalid,
        match="already been used",
    ):
        service.complete_tastytrade_oauth(
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
        service.TastytradeOAuthStateInvalid,
        match="expired",
    ):
        service.complete_tastytrade_oauth(
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
        service.get_tastytrade_connection(
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


def test_failed_token_exchange_consumes_state(
    db_session,
):
    user_id = uuid.uuid4()

    _begin(
        db_session,
        user_id,
    )

    def fail_exchange(
        code,
    ):
        raise (
            tastytrade_oauth_service
            .TastytradeOAuthError(
                "bad code"
            )
        )

    with pytest.raises(
        service.TastytradeConnectionError,
        match="token exchange failed",
    ):
        service.complete_tastytrade_oauth(
            db_session,
            state="raw-state-123",
            code="bad-code",
            now=NOW,
            token_exchange=(
                fail_exchange
            ),
        )

    connection = (
        service.get_tastytrade_connection(
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

    assert (
        connection.access_token_encrypted
        is None
    )

    assert (
        connection.refresh_token_encrypted
        is None
    )

    assert (
        connection.is_verified
        is False
    )


def test_state_is_bound_to_its_connection(
    db_session,
):
    first_user = uuid.uuid4()
    second_user = uuid.uuid4()

    _begin(
        db_session,
        first_user,
        state="first-state",
    )

    _begin(
        db_session,
        second_user,
        state="second-state",
    )

    service.complete_tastytrade_oauth(
        db_session,
        state="first-state",
        code="code-123",
        now=NOW,
        token_exchange=(
            _token_exchange
        ),
        broker_factory=(
            _broker_factory([
                _raw_account(
                    "11111111"
                ),
            ])
        ),
    )

    first_connection = (
        service.get_tastytrade_connection(
            db_session,
            user_id=first_user,
        )
    )

    second_connection = (
        service.get_tastytrade_connection(
            db_session,
            user_id=second_user,
        )
    )

    assert (
        first_connection.is_verified
        is True
    )

    assert (
        second_connection.is_verified
        is False
    )

    assert (
        second_connection
        .oauth_state_hash
        is not None
    )



def _make_tastytrade_selection_connection(
    session,
    *,
    user_id,
    first_number="TT1111",
    second_number="TT2222",
):
    connection = BrokerConnection(
        user_id=user_id,
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
        connection,
        first,
        second,
    )


def test_list_tastytrade_accounts_returns_active_accounts(
    db_session,
):
    user_id = uuid.uuid4()

    connection, first, second = (
        _make_tastytrade_selection_connection(
            db_session,
            user_id=user_id,
        )
    )

    inactive = BrokerAccount(
        broker_connection_id=connection.id,
        account_number="TT9999",
        nickname="Inactive",
        account_type="Business",
        is_default=False,
        is_active=False,
    )

    db_session.add(
        inactive
    )
    db_session.commit()

    result = service.list_tastytrade_accounts(
        db_session,
        user_id=user_id,
    )

    assert [
        item["account_number"]
        for item in result
    ] == [
        first.account_number,
        second.account_number,
    ]

    assert all(
        item["is_active"] is True
        for item in result
    )

    assert all(
        "refresh_token" not in item
        for item in result
    )

    assert all(
        "access_token" not in item
        for item in result
    )


def test_select_tastytrade_account_updates_default(
    db_session,
):
    user_id = uuid.uuid4()

    connection, first, second = (
        _make_tastytrade_selection_connection(
            db_session,
            user_id=user_id,
        )
    )

    result = service.select_tastytrade_account(
        db_session,
        user_id=user_id,
        account_id=second.id,
    )

    assert result["id"] == str(
        second.id
    )

    assert (
        result["account_number"]
        == second.account_number
    )

    assert result["is_default"] is True
    assert result["is_active"] is True

    db_session.refresh(
        connection
    )
    db_session.refresh(
        first
    )
    db_session.refresh(
        second
    )

    assert (
        connection.account_number
        == second.account_number
    )

    assert first.is_default is False
    assert second.is_default is True


def test_select_tastytrade_account_rejects_other_user_account(
    db_session,
):
    first_user_id = uuid.uuid4()
    second_user_id = uuid.uuid4()

    (
        _first_connection,
        _first_account,
        _first_second_account,
    ) = _make_tastytrade_selection_connection(
        db_session,
        user_id=first_user_id,
        first_number="USER1A",
        second_number="USER1B",
    )

    (
        _second_connection,
        foreign_account,
        _second_second_account,
    ) = _make_tastytrade_selection_connection(
        db_session,
        user_id=second_user_id,
        first_number="USER2A",
        second_number="USER2B",
    )

    with pytest.raises(
        service.TastytradeAccountSelectionError,
        match="Tastytrade account not found",
    ):
        service.select_tastytrade_account(
            db_session,
            user_id=first_user_id,
            account_id=foreign_account.id,
        )
