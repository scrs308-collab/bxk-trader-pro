import pytest
from fastapi import HTTPException, Request

from bxk_app.authorization import (
    OWNER_ACCESS_DETAIL,
    get_authenticated_user,
    require_owner,
)
from bxk_app.db_models.user import UserRole


def make_request(
    user=None,
) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/admin/test",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": (
                "testserver",
                80,
            ),
            "client": (
                "testclient",
                50000,
            ),
            "root_path": "",
        }
    )

    if user is not None:
        request.state.bxk_user = user

    return request


def test_owner_is_allowed():
    request = make_request(
        {
            "user_id": "owner-id",
            "username": "owner",
            "role": "OWNER",
            "auth_source": "DATABASE",
        }
    )

    user = require_owner(request)

    assert user["username"] == "owner"
    assert user["role"] == "OWNER"


def test_owner_enum_is_allowed():
    request = make_request(
        {
            "user_id": "owner-id",
            "username": "owner",
            "role": UserRole.OWNER,
        }
    )

    user = require_owner(request)

    assert user["role"] == UserRole.OWNER


@pytest.mark.parametrize(
    "role",
    [
        "BETA",
        "VIEWER",
    ],
)
def test_non_owner_roles_are_forbidden(
    role,
):
    request = make_request(
        {
            "user_id": "user-id",
            "username": "test-user",
            "role": role,
        }
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        require_owner(request)

    assert (
        exc_info.value.status_code
        == 403
    )

    assert (
        exc_info.value.detail
        == OWNER_ACCESS_DETAIL
    )


def test_missing_authenticated_user_is_forbidden():
    request = make_request()

    with pytest.raises(
        HTTPException
    ) as exc_info:
        require_owner(request)

    assert (
        exc_info.value.status_code
        == 403
    )


def test_malformed_authenticated_user_is_forbidden():
    request = make_request()

    request.state.bxk_user = (
        "definitely-not-a-user"
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        get_authenticated_user(
            request
        )

    assert (
        exc_info.value.status_code
        == 403
    )
