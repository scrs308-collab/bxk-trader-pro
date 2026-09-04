import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
)


class BrokerConnectionRequired(RuntimeError):
    pass


class BrokerConnectionInvalid(RuntimeError):
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


def resolve_tastytrade_broker(
    session: Session,
    *,
    user_context: dict,
) -> TastytradeBroker:
    """
    Resolve the broker belonging to the authenticated user.

    Security rules:

    - An active verified per-user connection always wins.
    - A malformed or unusable stored connection fails closed.
    - OWNER may use the historical global broker only when no
      per-user broker connection exists.
    - Non-OWNER users never fall back to the OWNER broker.
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
                    connection.client_secret_encrypted
                )
            )

            refresh_token = (
                decrypt_broker_secret(
                    connection.refresh_token_encrypted
                )
            )

        except BrokerCredentialError as exc:
            # Never fall back to another account if a stored
            # connection exists but cannot be decrypted.
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
        # Transitional compatibility path.
        #
        # Joe's existing production account continues using
        # Railway/global configuration until it is explicitly
        # migrated into broker_connections.
        return owner_broker

    raise BrokerConnectionRequired(
        "No Tastytrade account is connected for this user."
    )
