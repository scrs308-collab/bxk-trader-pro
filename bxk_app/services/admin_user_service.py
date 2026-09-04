from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bxk_app.db_models.broker_connection import (
    BrokerConnection,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


ALLOWED_ADMIN_CREATED_ROLES = {
    UserRole.BETA,
    UserRole.VIEWER,
}


def serialize_user(
    user: User,
) -> dict:
    """
    Return safe user information.

    Password hashes are intentionally never exposed.
    """

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": (
            user.role.value
            if isinstance(user.role, UserRole)
            else str(user.role)
        ),
        "is_active": bool(user.is_active),
        "must_change_password": bool(
            user.must_change_password
        ),
        "created_at": (
            user.created_at.isoformat()
            if user.created_at is not None
            else None
        ),
        "updated_at": (
            user.updated_at.isoformat()
            if user.updated_at is not None
            else None
        ),
    }


def list_users(
    session: Session,
) -> list[dict]:
    users = session.scalars(
        select(User).order_by(
            User.created_at.asc(),
            User.username.asc(),
        )
    ).all()

    return [
        serialize_user(user)
        for user in users
    ]


def create_user(
    session: Session,
    *,
    username: str,
    email: str,
    role: str,
    temporary_password: str,
) -> dict:
    username_value = str(
        username or ""
    ).strip()

    email_value = str(
        email or ""
    ).strip()

    role_value = str(
        role or ""
    ).strip().upper()

    password_value = str(
        temporary_password or ""
    )

    if not username_value:
        raise ValueError(
            "Username is required."
        )

    if len(username_value) > 100:
        raise ValueError(
            "Username must be 100 characters or fewer."
        )

    if not email_value:
        raise ValueError(
            "Email is required."
        )

    if (
        "@" not in email_value
        or email_value.startswith("@")
        or email_value.endswith("@")
        or len(email_value) > 320
    ):
        raise ValueError(
            "A valid email address is required."
        )

    try:
        user_role = UserRole(
            role_value
        )
    except ValueError as exc:
        raise ValueError(
            "Role must be BETA or VIEWER."
        ) from exc

    if (
        user_role
        not in ALLOWED_ADMIN_CREATED_ROLES
    ):
        raise ValueError(
            "Role must be BETA or VIEWER."
        )

    existing_username = session.scalar(
        select(User).where(
            func.lower(User.username)
            == username_value.casefold()
        )
    )

    if existing_username is not None:
        raise ValueError(
            "Username already exists."
        )

    existing_email = session.scalar(
        select(User).where(
            func.lower(User.email)
            == email_value.casefold()
        )
    )

    if existing_email is not None:
        raise ValueError(
            "Email already exists."
        )

    password_hash = hash_app_password(
        password_value
    )

    user = User(
        username=username_value,
        email=email_value,
        password_hash=password_hash,
        role=user_role,
        is_active=True,
        must_change_password=True,
    )

    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        raise ValueError(
            "Username or email already exists."
        ) from exc

    session.refresh(user)

    return serialize_user(user)

def set_user_active(
    session: Session,
    *,
    user_id: str,
    is_active: bool,
) -> dict:
    """
    Enable or disable a non-OWNER user account.

    OWNER accounts cannot be modified through this
    administrative endpoint.
    """

    import uuid

    try:
        parsed_user_id = uuid.UUID(
            str(user_id)
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Invalid user ID."
        ) from exc

    user = session.get(
        User,
        parsed_user_id,
    )

    if user is None:
        raise LookupError(
            "User not found."
        )

    role = (
        user.role
        if isinstance(
            user.role,
            UserRole,
        )
        else UserRole(
            str(user.role)
        )
    )

    if role == UserRole.OWNER:
        raise ValueError(
            "OWNER accounts cannot be "
            "enabled or disabled here."
        )

    user.is_active = bool(
        is_active
    )

    session.commit()
    session.refresh(user)

    return serialize_user(user)


def set_user_broker_live_trading(
    session: Session,
    *,
    user_id: str,
    enabled: bool,
) -> dict:
    """
    OWNER-controlled live-trading permission for one
    BETA user's verified Tastytrade connection.
    """

    import uuid

    try:
        parsed_user_id = uuid.UUID(
            str(user_id)
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Invalid user ID."
        ) from exc

    user = session.get(
        User,
        parsed_user_id,
    )

    if user is None:
        raise LookupError(
            "User not found."
        )

    role = (
        user.role
        if isinstance(
            user.role,
            UserRole,
        )
        else UserRole(
            str(user.role)
        )
    )

    if role != UserRole.BETA:
        raise ValueError(
            "Broker live trading can only be "
            "managed here for BETA users."
        )

    connection = session.scalar(
        select(BrokerConnection).where(
            BrokerConnection.user_id
            == parsed_user_id,
            BrokerConnection.broker
            == "tastytrade",
        )
    )

    if connection is None:
        raise LookupError(
            "Tastytrade connection not found "
            "for this user."
        )

    requested_enabled = bool(
        enabled
    )

    if requested_enabled and (
        not connection.is_active
        or not connection.is_verified
        or not str(
            connection.account_number
            or ""
        ).strip()
    ):
        raise ValueError(
            "Tastytrade connection must be active, "
            "verified, and have an account before "
            "live trading can be enabled."
        )

    connection.live_trading_enabled = (
        requested_enabled
    )

    session.commit()
    session.refresh(
        connection
    )

    return {
        "user_id": str(
            user.id
        ),
        "username": user.username,
        "broker": "tastytrade",
        "connected": bool(
            connection.is_active
            and connection.is_verified
        ),
        "verified": bool(
            connection.is_verified
        ),
        "live_trading_enabled": bool(
            connection.live_trading_enabled
        ),
    }

