from fastapi import HTTPException, Request

from bxk_app import config

from bxk_app.db_models.user import UserRole


OWNER_ACCESS_DETAIL = (
    "BXK OWNER access is required."
)

BROKER_OAUTH_ACCESS_DETAIL = (
    "Broker Connect has not been enabled "
    "for this BXK account."
)

SUBSCRIPTION_ACCESS_DETAIL = (
    "An active BXK Trader Pro subscription "
    "is required."
)


def get_authenticated_user(
    request: Request,
) -> dict:
    """
    Return the authenticated BXK user attached
    to the request by auth middleware.

    Authorization helpers intentionally fail closed
    if the request state is missing or malformed.
    """

    user = getattr(
        request.state,
        "bxk_user",
        None,
    )

    if not isinstance(user, dict):
        raise HTTPException(
            status_code=403,
            detail=OWNER_ACCESS_DETAIL,
        )

    return user


def require_owner(
    request: Request,
) -> dict:
    """
    Require an authenticated BXK OWNER.

    Works for both database-backed OWNER sessions
    and the temporary legacy CONFIG OWNER session
    because both expose role="OWNER".
    """

    user = get_authenticated_user(
        request
    )

    role = user.get("role")

    if isinstance(role, UserRole):
        role = role.value

    normalized_role = str(
        role or ""
    ).strip().upper()

    if normalized_role != UserRole.OWNER.value:
        raise HTTPException(
            status_code=403,
            detail=OWNER_ACCESS_DETAIL,
        )

    return user

def require_owner_or_beta(
    request: Request,
) -> dict:
    """
    Require an authenticated BXK user with access
    to private brokerage and trading operations.

    VIEWER users are intentionally excluded.
    """

    user = get_authenticated_user(
        request
    )

    role = user.get("role")

    if isinstance(role, UserRole):
        role = role.value

    normalized_role = str(
        role or ""
    ).strip().upper()

    if normalized_role not in {
        UserRole.OWNER.value,
        UserRole.BETA.value,
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "BXK trading access requires "
                "OWNER or BETA permission."
            ),
        )

    if (
        normalized_role != UserRole.OWNER.value
        and config
        .BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED
    ):
        subscription = user.get(
            "subscription"
        )

        if (
            not isinstance(subscription, dict)
            or subscription.get(
                "access_granted"
            ) is not True
        ):
            raise HTTPException(
                status_code=402,
                detail=(
                    SUBSCRIPTION_ACCESS_DETAIL
                ),
            )

    return user


def require_broker_oauth_access(
    request: Request,
) -> dict:
    """
    Allow Broker Connect for OWNER accounts and
    individually approved BETA accounts.

    The permission is loaded from the database on
    every authenticated request, so OWNER changes
    take effect without forcing the user to sign in
    again. VIEWER accounts always fail closed.
    """

    user = get_authenticated_user(
        request
    )

    role = user.get("role")

    if isinstance(role, UserRole):
        role = role.value

    normalized_role = str(
        role or ""
    ).strip().upper()

    if normalized_role == UserRole.OWNER.value:
        return user

    if (
        normalized_role == UserRole.BETA.value
        and user.get("broker_oauth_enabled")
        is True
    ):
        return user

    raise HTTPException(
        status_code=403,
        detail=BROKER_OAUTH_ACCESS_DETAIL,
    )


def require_owner_or_auth_disabled(
    request: Request,
) -> dict:
    """
    Require OWNER access when BXK authentication
    is enabled.

    Auth-disabled local development preserves the
    historical single-user OWNER behavior.
    """

    if not config.BXK_AUTH_ENABLED:
        return {
            "user_id": None,
            "username": "local",
            "role": UserRole.OWNER.value,
            "auth_source": "AUTH_DISABLED",
        }

    return require_owner(request)


def has_owner_access(
    request: Request,
) -> bool:
    """
    Return whether this request may receive the
    global OWNER account context.
    """

    if not config.BXK_AUTH_ENABLED:
        return True

    user = getattr(
        request.state,
        "bxk_user",
        None,
    )

    if not isinstance(user, dict):
        return False

    role = user.get("role")

    if isinstance(role, UserRole):
        role = role.value

    return (
        str(role or "")
        .strip()
        .upper()
        == UserRole.OWNER.value
    )
