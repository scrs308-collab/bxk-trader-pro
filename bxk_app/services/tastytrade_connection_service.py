import hashlib
import secrets
import time
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
)
from bxk_app.db_models.broker_account import (
    BrokerAccount,
)
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.services import (
    tastytrade_oauth_service,
)
from bxk_app.services.broker_credential_service import (
    BrokerCredentialError,
    encrypt_broker_secret,
)


TASTYTRADE_BROKER_NAME = "tastytrade"
TASTYTRADE_STATE_TTL_MINUTES = 10


class TastytradeConnectionError(
    RuntimeError
):
    pass


class TastytradeOAuthStateInvalid(
    TastytradeConnectionError
):
    pass


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _normalize_datetime(
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


def _state_hash(
    raw_state: str,
) -> str:
    return hashlib.sha256(
        str(raw_state).encode(
            "utf-8"
        )
    ).hexdigest()


def get_tastytrade_connection(
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
            == TASTYTRADE_BROKER_NAME,
        )
    )

    return session.scalar(
        statement
    )


def begin_tastytrade_oauth(
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
        raise TastytradeConnectionError(
            "Could not generate Tastytrade OAuth state."
        )

    builder = (
        authorization_url_builder
        or tastytrade_oauth_service
        .build_authorization_url
    )

    authorization_url = builder(
        raw_state
    )

    expires_at = (
        current_time
        + timedelta(
            minutes=(
                TASTYTRADE_STATE_TTL_MINUTES
            )
        )
    )

    connection = (
        get_tastytrade_connection(
            session,
            user_id=user_id,
        )
    )

    if connection is None:
        connection = BrokerConnection(
            user_id=user_id,
            broker=TASTYTRADE_BROKER_NAME,
            client_secret_encrypted=None,
            refresh_token_encrypted=None,
            access_token_encrypted=None,
            account_number=None,
            base_url=(
                config.TASTYTRADE_BASE_URL
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
        _state_hash(
            raw_state
        )
    )

    connection.oauth_state_expires_at = (
        expires_at
    )

    session.commit()

    return {
        "broker":
            TASTYTRADE_BROKER_NAME,
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
            == TASTYTRADE_BROKER_NAME,
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


def cancel_tastytrade_oauth(
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


def _normalize_accounts(
    raw_accounts,
) -> list[dict]:
    normalized = []
    seen_numbers = set()

    for item in (
        raw_accounts
        or []
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        account = (
            item.get("account")
            or item
        )

        if not isinstance(
            account,
            dict,
        ):
            continue

        account_number = str(
            account.get(
                "account-number"
            )
            or account.get(
                "account_number"
            )
            or ""
        ).strip()

        if (
            not account_number
            or account_number
            in seen_numbers
        ):
            continue

        seen_numbers.add(
            account_number
        )

        nickname = str(
            account.get("nickname")
            or ""
        ).strip()

        account_type = str(
            account.get(
                "account-type-name"
            )
            or account.get(
                "account-type"
            )
            or account.get(
                "account_type"
            )
            or ""
        ).strip()

        normalized.append({
            "account_number":
                account_number,
            "broker_account_key":
                None,
            "nickname": (
                nickname
                or None
            ),
            "account_type": (
                account_type
                or None
            ),
        })

    return normalized


def _sync_accounts(
    session: Session,
    *,
    connection: BrokerConnection,
    discovered_accounts,
) -> list[BrokerAccount]:
    normalized = (
        _normalize_accounts(
            discovered_accounts
        )
    )

    existing = list(
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

    existing_by_number = {
        account.account_number:
            account
        for account in existing
    }

    discovered_numbers = {
        item["account_number"]
        for item in normalized
    }

    for account in existing:
        if (
            account.account_number
            not in discovered_numbers
        ):
            account.is_active = False
            account.is_default = False

    synchronized = []

    for item in normalized:
        account_number = (
            item["account_number"]
        )

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
                nickname=(
                    item["nickname"]
                ),
                account_type=(
                    item[
                        "account_type"
                    ]
                ),
                is_default=False,
                is_active=True,
            )

            session.add(
                account
            )
        else:
            account.broker_account_key = (
                item[
                    "broker_account_key"
                ]
            )

            account.nickname = (
                item["nickname"]
            )

            account.account_type = (
                item[
                    "account_type"
                ]
            )

            account.is_active = True

        synchronized.append(
            account
        )

    previous_selected = str(
        connection.account_number
        or ""
    ).strip()

    active_numbers = {
        account.account_number
        for account in synchronized
    }

    selected_account = None

    if (
        previous_selected
        and previous_selected
        in active_numbers
    ):
        selected_account = (
            previous_selected
        )
    elif len(
        synchronized
    ) == 1:
        selected_account = (
            synchronized[0]
            .account_number
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


def _default_broker_factory(
    *,
    access_token: str,
    refresh_token: str,
    account_number=None,
):
    broker = TastytradeBroker(
        client_secret=(
            config.TASTYTRADE_CLIENT_SECRET
        ),
        refresh_token=(
            refresh_token
        ),
        account_number=(
            account_number
        ),
        base_url=(
            config.TASTYTRADE_BASE_URL
        ),
        live_trading_enabled=False,
    )

    # The authorization-code exchange already supplied
    # a valid short-lived access token. Seed the broker
    # with it so account discovery does not immediately
    # perform another refresh-token exchange.
    broker.access_token = (
        access_token
    )

    broker.token_created_at = (
        time.time()
    )

    return broker


def complete_tastytrade_oauth(
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
        raise TastytradeOAuthStateInvalid(
            "Tastytrade OAuth state is missing."
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
        raise TastytradeOAuthStateInvalid(
            "Tastytrade OAuth state is invalid "
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

        raise TastytradeOAuthStateInvalid(
            "Tastytrade OAuth state has expired."
        )

    # Consume before contacting Tastytrade.
    # Each callback state is valid exactly once,
    # even when the downstream exchange fails.
    _consume_oauth_state(
        session,
        connection,
    )

    exchange = (
        token_exchange
        or tastytrade_oauth_service
        .exchange_authorization_code
    )

    try:
        tokens = exchange(
            code
        )
    except (
        tastytrade_oauth_service
        .TastytradeOAuthError
    ) as exc:
        raise TastytradeConnectionError(
            "Tastytrade token exchange failed."
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
        raise TastytradeConnectionError(
            "Tastytrade access-token lifetime "
            "is invalid."
        ) from exc

    if (
        not access_token
        or not refresh_token
        or expires_in <= 0
    ):
        raise TastytradeConnectionError(
            "Tastytrade token response is incomplete."
        )

    factory = (
        broker_factory
        or _default_broker_factory
    )

    broker = factory(
        access_token=access_token,
        refresh_token=refresh_token,
        account_number=None,
    )

    accounts = broker.get_accounts()

    if not accounts:
        raise TastytradeConnectionError(
            "Tastytrade account discovery failed."
        )

    try:
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
    except BrokerCredentialError as exc:
        raise TastytradeConnectionError(
            "Tastytrade OAuth tokens could not "
            "be stored securely."
        ) from exc

    synchronized = _sync_accounts(
        session,
        connection=connection,
        discovered_accounts=accounts,
    )

    if not synchronized:
        raise TastytradeConnectionError(
            "No Tastytrade accounts were returned."
        )

    connection.client_secret_encrypted = None

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

    # Tastytrade OAuth refresh tokens remain valid
    # for the life of the grant unless revoked.
    connection.refresh_token_expires_at = None

    connection.base_url = (
        config.TASTYTRADE_BASE_URL
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
        for account in synchronized
    ]

    return {
        "broker":
            TASTYTRADE_BROKER_NAME,
        "connected":
            True,
        "verified":
            True,
        "account_number":
            connection.account_number,
        "accounts":
            account_result,
    }
