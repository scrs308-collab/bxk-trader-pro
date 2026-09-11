import hashlib
import secrets
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app.brokers.schwab import SchwabBroker
from bxk_app.db_models.broker_account import (
    BrokerAccount,
)
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.services import schwab_oauth_service
from bxk_app.services.broker_credential_service import (
    encrypt_broker_secret,
)


SCHWAB_BROKER_NAME = "schwab"

SCHWAB_STATE_TTL_MINUTES = 10

SCHWAB_REFRESH_TOKEN_TTL_DAYS = 7


class SchwabConnectionError(RuntimeError):
    pass


class SchwabOAuthStateInvalid(
    SchwabConnectionError
):
    pass


def _utc_now():
    return datetime.now(
        timezone.utc
    )


def _normalize_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _state_hash(state: str) -> str:
    return hashlib.sha256(
        state.encode("utf-8")
    ).hexdigest()


def get_schwab_connection(
    session: Session,
    *,
    user_id,
) -> BrokerConnection | None:
    statement = (
        select(BrokerConnection)
        .where(
            BrokerConnection.user_id
            == user_id,
            BrokerConnection.broker
            == SCHWAB_BROKER_NAME,
        )
    )

    return session.scalar(
        statement
    )


def begin_schwab_oauth(
    session: Session,
    *,
    user_id,
    now=None,
    state_factory=None,
    authorization_url_builder=None,
) -> dict:
    current_time = (
        _normalize_datetime(now)
        or _utc_now()
    )

    factory = (
        state_factory
        or (
            lambda:
                secrets.token_urlsafe(32)
        )
    )

    raw_state = str(
        factory()
        or ""
    ).strip()

    if not raw_state:
        raise SchwabConnectionError(
            "Could not generate Schwab OAuth state."
        )

    builder = (
        authorization_url_builder
        or schwab_oauth_service
        .build_authorization_url
    )

    authorization_url = builder(
        raw_state
    )

    hashed_state = _state_hash(
        raw_state
    )

    expires_at = (
        current_time
        + timedelta(
            minutes=(
                SCHWAB_STATE_TTL_MINUTES
            )
        )
    )

    connection = get_schwab_connection(
        session,
        user_id=user_id,
    )

    if connection is None:
        connection = BrokerConnection(
            user_id=user_id,
            broker=SCHWAB_BROKER_NAME,
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            access_token_encrypted=None,
            account_number=None,
            base_url=(
                SchwabBroker.DEFAULT_BASE_URL
            ),
            is_active=True,
            is_verified=False,
            live_trading_enabled=False,
        )

        session.add(
            connection
        )
    else:
        connection.is_active = True

    connection.oauth_state_hash = (
        hashed_state
    )

    connection.oauth_state_expires_at = (
        expires_at
    )

    session.commit()

    return {
        "broker":
            SCHWAB_BROKER_NAME,
        "authorization_url":
            authorization_url,
        "expires_at":
            expires_at,
        "connection_id":
            str(connection.id),
    }


def _find_connection_by_state(
    session: Session,
    *,
    state_hash: str,
) -> BrokerConnection | None:
    statement = (
        select(BrokerConnection)
        .where(
            BrokerConnection.broker
            == SCHWAB_BROKER_NAME,
            BrokerConnection.oauth_state_hash
            == state_hash,
        )
    )

    return session.scalar(
        statement
    )


def _consume_oauth_state(
    session: Session,
    connection: BrokerConnection,
):
    connection.oauth_state_hash = None
    connection.oauth_state_expires_at = None

    session.commit()


def _sync_accounts(
    session: Session,
    *,
    connection: BrokerConnection,
    discovered_accounts: list[dict],
) -> list[BrokerAccount]:
    normalized_accounts = []

    seen_numbers = set()

    for item in discovered_accounts:
        if not isinstance(
            item,
            dict,
        ):
            continue

        account_number = str(
            item.get(
                "account_number"
            )
            or ""
        ).strip()

        account_key = str(
            item.get(
                "broker_account_key"
            )
            or ""
        ).strip()

        if (
            not account_number
            or not account_key
            or account_number
            in seen_numbers
        ):
            continue

        seen_numbers.add(
            account_number
        )

        normalized_accounts.append({
            "account_number":
                account_number,
            "broker_account_key":
                account_key,
        })

    if not normalized_accounts:
        raise SchwabConnectionError(
            "Schwab returned no authorized accounts."
        )

    statement = (
        select(BrokerAccount)
        .where(
            BrokerAccount
            .broker_connection_id
            == connection.id
        )
    )

    existing_accounts = list(
        session.scalars(
            statement
        ).all()
    )

    existing_by_number = {
        account.account_number:
            account
        for account in existing_accounts
    }

    active_numbers = {
        item["account_number"]
        for item in normalized_accounts
    }

    previous_default = (
        connection.account_number
        if connection.account_number
        in active_numbers
        else None
    )

    if previous_default is None:
        previous_defaults = [
            account.account_number
            for account
            in existing_accounts
            if (
                account.is_default
                and account.account_number
                in active_numbers
            )
        ]

        if len(
            previous_defaults
        ) == 1:
            previous_default = (
                previous_defaults[0]
            )

    synchronized = []

    for item in normalized_accounts:
        account_number = item[
            "account_number"
        ]

        account = (
            existing_by_number.get(
                account_number
            )
        )

        if account is None:
            account = BrokerAccount(
                broker_connection_id=(
                    connection.id
                ),
                account_number=(
                    account_number
                ),
                broker_account_key=(
                    item[
                        "broker_account_key"
                    ]
                ),
                is_default=False,
                is_active=True,
            )

            session.add(
                account
            )

            existing_by_number[
                account_number
            ] = account
        else:
            account.broker_account_key = (
                item[
                    "broker_account_key"
                ]
            )

            account.is_active = True

        synchronized.append(
            account
        )

    for account in existing_accounts:
        if (
            account.account_number
            not in active_numbers
        ):
            account.is_active = False
            account.is_default = False

    selected_account = (
        previous_default
    )

    if (
        selected_account is None
        and len(
            normalized_accounts
        ) == 1
    ):
        selected_account = (
            normalized_accounts[0][
                "account_number"
            ]
        )

    for account in synchronized:
        account.is_default = bool(
            selected_account
            and account.account_number
            == selected_account
        )

    connection.account_number = (
        selected_account
    )

    return synchronized


def complete_schwab_oauth(
    session: Session,
    *,
    state: str,
    code: str,
    now=None,
    token_exchange=None,
    broker_factory=None,
) -> dict:
    clean_state = str(
        state or ""
    ).strip()

    if not clean_state:
        raise SchwabOAuthStateInvalid(
            "Schwab OAuth state is missing."
        )

    current_time = (
        _normalize_datetime(now)
        or _utc_now()
    )

    connection = (
        _find_connection_by_state(
            session,
            state_hash=_state_hash(
                clean_state
            ),
        )
    )

    if connection is None:
        raise SchwabOAuthStateInvalid(
            "Schwab OAuth state is invalid "
            "or has already been used."
        )

    state_expires_at = (
        _normalize_datetime(
            connection
            .oauth_state_expires_at
        )
    )

    if (
        state_expires_at is None
        or state_expires_at
        <= current_time
    ):
        _consume_oauth_state(
            session,
            connection,
        )

        raise SchwabOAuthStateInvalid(
            "Schwab OAuth state has expired."
        )

    # Consume before any external request.
    # A callback state is valid exactly once.
    _consume_oauth_state(
        session,
        connection,
    )

    exchange = (
        token_exchange
        or schwab_oauth_service
        .exchange_authorization_code
    )

    try:
        tokens = exchange(
            code
        )
    except (
        schwab_oauth_service
        .SchwabOAuthError
    ) as exc:
        raise SchwabConnectionError(
            "Schwab token exchange failed."
        ) from exc

    access_token = str(
        tokens.get(
            "access_token"
        )
        or ""
    ).strip()

    refresh_token = str(
        tokens.get(
            "refresh_token"
        )
        or ""
    ).strip()

    try:
        expires_in = int(
            tokens.get(
                "expires_in",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SchwabConnectionError(
            "Schwab access-token lifetime "
            "is invalid."
        ) from exc

    if (
        not access_token
        or not refresh_token
        or expires_in <= 0
    ):
        raise SchwabConnectionError(
            "Schwab token response is incomplete."
        )

    factory = (
        broker_factory
        or SchwabBroker
    )

    broker = factory(
        access_token=access_token,
        account_number=None,
    )

    accounts = broker.get_accounts(
        force=True
    )

    if not accounts:
        detail = str(
            getattr(
                broker,
                "last_error",
                "",
            )
            or ""
        ).strip()

        message = (
            "Schwab account discovery failed."
        )

        if detail:
            message = (
                f"{message} {detail}"
            )

        raise SchwabConnectionError(
            message
        )

    encrypted_access_token = (
        encrypt_broker_secret(
            access_token
        )
    )

    encrypted_refresh_token = (
        encrypt_broker_secret(
            refresh_token
        )
    )

    synchronized = _sync_accounts(
        session,
        connection=connection,
        discovered_accounts=accounts,
    )

    connection.access_token_encrypted = (
        encrypted_access_token
    )

    connection.refresh_token_encrypted = (
        encrypted_refresh_token
    )

    connection.access_token_expires_at = (
        current_time
        + timedelta(
            seconds=expires_in
        )
    )

    connection.refresh_token_expires_at = (
        current_time
        + timedelta(
            days=(
                SCHWAB_REFRESH_TOKEN_TTL_DAYS
            )
        )
    )

    connection.is_active = True
    connection.is_verified = True
    connection.last_verified_at = (
        current_time
    )

    session.commit()

    account_result = [
        {
            "account_number":
                account.account_number,
            "broker_account_key":
                account.broker_account_key,
            "is_default":
                bool(
                    account.is_default
                ),
        }
        for account in synchronized
    ]

    return {
        "broker":
            SCHWAB_BROKER_NAME,
        "connected":
            True,
        "verified":
            True,
        "connection_id":
            str(connection.id),
        "account_number":
            connection.account_number,
        "accounts":
            account_result,
    }


class SchwabAccountSelectionError(
    SchwabConnectionError
):
    pass


def cancel_schwab_oauth(
    session: Session,
    *,
    state: str,
) -> bool:
    clean_state = str(
        state or ""
    ).strip()

    if not clean_state:
        return False

    connection = (
        _find_connection_by_state(
            session,
            state_hash=_state_hash(
                clean_state
            ),
        )
    )

    if connection is None:
        return False

    _consume_oauth_state(
        session,
        connection,
    )

    return True


def list_schwab_accounts(
    session: Session,
    *,
    user_id,
) -> list[dict]:
    connection = get_schwab_connection(
        session,
        user_id=user_id,
    )

    if connection is None:
        return []

    statement = (
        select(BrokerAccount)
        .where(
            BrokerAccount
            .broker_connection_id
            == connection.id,
            BrokerAccount.is_active
            .is_(True),
        )
        .order_by(
            BrokerAccount.account_number
        )
    )

    accounts = list(
        session.scalars(
            statement
        ).all()
    )

    return [
        {
            "id":
                str(account.id),
            "account_number":
                account.account_number,
            "broker_account_key":
                account.broker_account_key,
            "nickname":
                account.nickname,
            "account_type":
                account.account_type,
            "is_default":
                bool(
                    account.is_default
                ),
            "is_active":
                bool(
                    account.is_active
                ),
        }
        for account in accounts
    ]


def select_schwab_account(
    session: Session,
    *,
    user_id,
    account_id,
) -> dict:
    connection = get_schwab_connection(
        session,
        user_id=user_id,
    )

    if connection is None:
        raise SchwabAccountSelectionError(
            "Schwab account not found."
        )

    selected = session.scalar(
        select(BrokerAccount)
        .where(
            BrokerAccount.id
            == account_id,
            BrokerAccount
            .broker_connection_id
            == connection.id,
            BrokerAccount.is_active
            .is_(True),
        )
    )

    if selected is None:
        raise SchwabAccountSelectionError(
            "Schwab account not found."
        )

    accounts = list(
        session.scalars(
            select(BrokerAccount)
            .where(
                BrokerAccount
                .broker_connection_id
                == connection.id,
                BrokerAccount.is_active
                .is_(True),
            )
        ).all()
    )

    for account in accounts:
        account.is_default = (
            account.id
            == selected.id
        )

    connection.account_number = (
        selected.account_number
    )

    session.commit()

    return {
        "id":
            str(selected.id),
        "account_number":
            selected.account_number,
        "nickname":
            selected.nickname,
        "account_type":
            selected.account_type,
        "is_default":
            True,
        "is_active":
            True,
    }

