from fastapi import HTTPException, Request

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
