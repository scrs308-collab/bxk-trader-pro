from fastapi import HTTPException, Request

from bxk_app import config

from bxk_app.db_models.user import UserRole


OWNER_ACCESS_DETAIL = (
    "BXK OWNER access is required."
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
