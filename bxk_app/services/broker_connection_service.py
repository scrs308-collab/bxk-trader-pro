import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
    broker as owner_broker,
)
from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.db_models.user import UserRole
from bxk_app.services.broker_credential_service import (
    BrokerCredentialError,
    decrypt_broker_secret,
    encrypt_broker_secret,
)


class BrokerConnectionRequired(RuntimeError):
    pass


class BrokerConnectionInvalid(RuntimeError):
    pass


class BrokerVerificationError(RuntimeError):
    pass


def _normalized_role(
    user_context: dict,
) -> str:
    role = user_context.get("role")

    if isinstance(role, UserRole):
        role = role.value

    return str(
        role or ""
    ).strip().upper()


def _normalized_user_id(
    user_context: dict,
) -> uuid.UUID | None:
    raw_user_id = user_context.get(
        "user_id"
    )

    if raw_user_id in (
        None,
        "",
    ):
        return None

    if isinstance(
        raw_user_id,
        uuid.UUID,
    ):
        return raw_user_id

    try:
        return uuid.UUID(
            str(raw_user_id)
        )
    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as exc:
        raise BrokerConnectionInvalid(
            "Authenticated user ID is invalid."
        ) from exc


def _mask_account_number(
    account_number: str | None,
) -> str | None:
    value = str(
        account_number or ""
    ).strip()

    if not value:
        return None

    if len(value) <= 4:
        return "*" * len(value)

    return (
        "*" * (len(value) - 4)
        + value[-4:]
    )


def get_any_user_tastytrade_connection(
    session: Session,
    *,
    user_id: uuid.UUID,
) -> BrokerConnection | None:
    statement = (
        select(BrokerConnection)
        .where(
            BrokerConnection.user_id
            == user_id,
            BrokerConnection.broker
            == "tastytrade",
        )
    )

    return session.scalar(
        statement
    )


def get_user_tastytrade_connection(
    session: Session,
    *,
    user_id: uuid.UUID,
) -> BrokerConnection | None:
    statement = (
        select(BrokerConnection)
        .where(
            BrokerConnection.user_id
            == user_id,
            BrokerConnection.broker
            == "tastytrade",
            BrokerConnection.is_active.is_(
                True
            ),
        )
    )

    return session.scalar(
        statement
    )


def _extract_tastytrade_accounts(
    raw_accounts: list[dict],
) -> list[dict]:
    accounts = []

    for item in raw_accounts:
        account = (
            (item or {}).get("account")
            or {}
        )

        account_number = str(
            account.get("account-number")
            or account.get("account_number")
            or ""
        ).strip()

        if not account_number:
            continue

        accounts.append(
            {
                "account_number":
                    account_number,
                "nickname": str(
                    account.get("nickname")
                    or ""
                ),
            }
        )

    return accounts


def verify_tastytrade_credentials(
    *,
    client_secret: str,
    refresh_token: str,
) -> list[dict]:
    clean_client_secret = str(
        client_secret or ""
    ).strip()

    clean_refresh_token = str(
        refresh_token or ""
    ).strip()

    if not clean_client_secret:
        raise BrokerVerificationError(
            "Tastytrade client secret is required."
        )

    if not clean_refresh_token:
        raise BrokerVerificationError(
            "Tastytrade refresh token is required."
        )

    temporary_broker = TastytradeBroker(
        client_secret=clean_client_secret,
        refresh_token=clean_refresh_token,
        account_number="",
        base_url=config.TASTYTRADE_BASE_URL,
        live_trading_enabled=False,
    )

    if not temporary_broker.authenticate(
        force=True
    ):
        raise BrokerVerificationError(
            "Tastytrade authentication failed."
        )

    accounts = (
        _extract_tastytrade_accounts(
            temporary_broker.get_accounts()
        )
    )

    if not accounts:
        raise BrokerVerificationError(
            "No Tastytrade accounts were returned."
        )

    return accounts


def _connection_status(
    connection: BrokerConnection,
) -> dict:
    return {
        "broker": "tastytrade",
        "connected": bool(
            connection.is_active
            and connection.is_verified
        ),
        "verified": bool(
            connection.is_verified
        ),
        "source": "user_connection",
        "account_number_masked":
            _mask_account_number(
                connection.account_number
            ),
        "live_trading_enabled": bool(
            connection.live_trading_enabled
            and config.BXK_LIVE_TRADING_ENABLED
        ),
        "user_live_trading_enabled": bool(
            connection.live_trading_enabled
        ),
        "global_live_trading_enabled": bool(
            config.BXK_LIVE_TRADING_ENABLED
        ),
        "last_verified_at":
            connection.last_verified_at,
    }


def get_broker_connection_status(
    session: Session,
    *,
    user_context: dict,
) -> dict:
    role = _normalized_role(
        user_context
    )

    user_id = _normalized_user_id(
        user_context
    )

    connection = None

    if user_id is not None:
        connection = (
            get_any_user_tastytrade_connection(
                session,
                user_id=user_id,
            )
        )

    if connection is not None:
        return _connection_status(
            connection
        )

    if role == UserRole.OWNER.value:
        legacy_configured = bool(
            str(
                config.TASTYTRADE_CLIENT_SECRET
                or ""
            ).strip()
            and str(
                config.TASTYTRADE_REFRESH_TOKEN
                or ""
            ).strip()
            and str(
                config.TASTYTRADE_ACCOUNT_NUMBER
                or ""
            ).strip()
        )

        return {
            "broker": "tastytrade",
            "connected":
                legacy_configured,
            "verified":
                legacy_configured,
            "source": (
                "legacy_owner"
                if legacy_configured
                else "none"
            ),
            "account_number_masked":
                _mask_account_number(
                    config
                    .TASTYTRADE_ACCOUNT_NUMBER
                ),
            "live_trading_enabled": bool(
                legacy_configured
                and config
                .BXK_LIVE_TRADING_ENABLED
            ),
            "user_live_trading_enabled":
                None,
            "global_live_trading_enabled":
                bool(
                    config
                    .BXK_LIVE_TRADING_ENABLED
                ),
            "last_verified_at": None,
        }

    return {
        "broker": "tastytrade",
        "connected": False,
        "verified": False,
        "source": "none",
        "account_number_masked": None,
        "live_trading_enabled": False,
        "user_live_trading_enabled":
            False,
        "global_live_trading_enabled":
            bool(
                config
                .BXK_LIVE_TRADING_ENABLED
            ),
        "last_verified_at": None,
    }


def connect_tastytrade_account(
    session: Session,
    *,
    user_context: dict,
    client_secret: str,
    refresh_token: str,
    account_number: str | None = None,
) -> dict:
    user_id = _normalized_user_id(
        user_context
    )

    if user_id is None:
        raise BrokerConnectionInvalid(
            "A database-backed user account is required."
        )

    accounts = verify_tastytrade_credentials(
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    requested_account = str(
        account_number or ""
    ).strip()

    if not requested_account:
        if len(accounts) != 1:
            raise BrokerVerificationError(
                "Multiple Tastytrade accounts were found. "
                "Select an account number."
            )

        requested_account = (
            accounts[0]["account_number"]
        )

    valid_numbers = {
        item["account_number"]
        for item in accounts
    }

    if requested_account not in valid_numbers:
        raise BrokerVerificationError(
            "The selected account was not returned "
            "for these Tastytrade credentials."
        )

    encrypted_client_secret = (
        encrypt_broker_secret(
            str(client_secret).strip()
        )
    )

    encrypted_refresh_token = (
        encrypt_broker_secret(
            str(refresh_token).strip()
        )
    )

    connection = (
        get_any_user_tastytrade_connection(
            session,
            user_id=user_id,
        )
    )

    now = datetime.now(
        timezone.utc
    )

    if connection is None:
        connection = BrokerConnection(
            user_id=user_id,
            broker="tastytrade",
            client_secret_encrypted=(
                encrypted_client_secret
            ),
            refresh_token_encrypted=(
                encrypted_refresh_token
            ),
            account_number=(
                requested_account
            ),
            base_url=(
                config.TASTYTRADE_BASE_URL
            ),
            is_active=True,
            is_verified=True,
            live_trading_enabled=False,
            last_verified_at=now,
        )

        session.add(
            connection
        )

    else:
        connection.client_secret_encrypted = (
            encrypted_client_secret
        )

        connection.refresh_token_encrypted = (
            encrypted_refresh_token
        )

        connection.account_number = (
            requested_account
        )

        connection.base_url = (
            config.TASTYTRADE_BASE_URL
        )

        connection.is_active = True
        connection.is_verified = True
        connection.last_verified_at = now

    session.commit()
    session.refresh(
        connection
    )

    return _connection_status(
        connection
    )


def disconnect_tastytrade_account(
    session: Session,
    *,
    user_context: dict,
) -> bool:
    user_id = _normalized_user_id(
        user_context
    )

    if user_id is None:
        raise BrokerConnectionInvalid(
            "A database-backed user account is required."
        )

    connection = (
        get_any_user_tastytrade_connection(
            session,
            user_id=user_id,
        )
    )

    if connection is None:
        return False

    session.delete(
        connection
    )

    session.commit()

    return True


def resolve_tastytrade_broker(
    session: Session,
    *,
    user_context: dict,
) -> TastytradeBroker:
    """
    Resolve the broker belonging to the authenticated user.

    Non-OWNER users never fall back to the global OWNER broker.
    """

    if not isinstance(
        user_context,
        dict,
    ):
        raise BrokerConnectionInvalid(
            "Authenticated user context is invalid."
        )

    role = _normalized_role(
        user_context
    )

    user_id = _normalized_user_id(
        user_context
    )

    connection = None

    if user_id is not None:
        connection = (
            get_user_tastytrade_connection(
                session,
                user_id=user_id,
            )
        )

    if connection is not None:
        if not connection.is_verified:
            raise BrokerConnectionRequired(
                "Tastytrade connection has not been verified."
            )

        try:
            client_secret = (
                decrypt_broker_secret(
                    connection
                    .client_secret_encrypted
                )
            )

            refresh_token = (
                decrypt_broker_secret(
                    connection
                    .refresh_token_encrypted
                )
            )

        except BrokerCredentialError as exc:
            raise BrokerConnectionInvalid(
                "Stored Tastytrade credentials are unavailable."
            ) from exc

        return TastytradeBroker(
            client_secret=client_secret,
            refresh_token=refresh_token,
            account_number=(
                connection.account_number
            ),
            base_url=(
                connection.base_url
            ),
            live_trading_enabled=(
                connection.live_trading_enabled
            ),
        )

    if role == UserRole.OWNER.value:
        return owner_broker

    raise BrokerConnectionRequired(
        "No Tastytrade account is connected for this user."
    )
