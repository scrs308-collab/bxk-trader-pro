import pytest
from fastapi import HTTPException, Request

from bxk_app.authorization import (
    BROKER_OAUTH_ACCESS_DETAIL,
    OWNER_ACCESS_DETAIL,
    SUBSCRIPTION_ACCESS_DETAIL,
    get_authenticated_user,
    require_broker_oauth_access,
    require_owner,
    require_owner_or_beta,
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


def test_owner_has_broker_oauth_access():
    request = make_request(
        {
            "user_id": "owner-id",
            "username": "owner",
            "role": "OWNER",
            "broker_oauth_enabled": False,
        }
    )

    assert (
        require_broker_oauth_access(
            request
        )["username"]
        == "owner"
    )


def test_approved_beta_has_broker_oauth_access():
    request = make_request(
        {
            "user_id": "beta-id",
            "username": "kdixon",
            "role": "BETA",
            "broker_oauth_enabled": True,
        }
    )

    assert (
        require_broker_oauth_access(
            request
        )["username"]
        == "kdixon"
    )


@pytest.mark.parametrize(
    "user",
    [
        {
            "role": "BETA",
            "broker_oauth_enabled": False,
        },
        {
            "role": "VIEWER",
            "broker_oauth_enabled": True,
        },
    ],
)
def test_unapproved_user_lacks_broker_oauth_access(
    user,
):
    request = make_request(user)

    with pytest.raises(
        HTTPException
    ) as exc_info:
        require_broker_oauth_access(
            request
        )

    assert exc_info.value.status_code == 403
    assert (
        exc_info.value.detail
        == BROKER_OAUTH_ACCESS_DETAIL
    )


def test_subscription_enforcement_blocks_unpaid_beta(
    monkeypatch,
):
    monkeypatch.setattr(
        "bxk_app.config."
        "BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED",
        True,
    )

    request = make_request(
        {
            "role": "BETA",
            "subscription": {
                "access_granted": False,
            },
        }
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        require_owner_or_beta(request)

    assert exc_info.value.status_code == 402
    assert (
        exc_info.value.detail
        == SUBSCRIPTION_ACCESS_DETAIL
    )


def test_subscription_enforcement_allows_paid_beta(
    monkeypatch,
):
    monkeypatch.setattr(
        "bxk_app.config."
        "BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED",
        True,
    )

    request = make_request(
        {
            "role": "BETA",
            "subscription": {
                "access_granted": True,
            },
        }
    )

    assert (
        require_owner_or_beta(request)["role"]
        == "BETA"
    )
