from urllib.parse import (
    parse_qs,
    urlparse,
)

import pytest
import requests

from bxk_app import config
from bxk_app.services import (
    schwab_oauth_service as service,
)


class FakeResponse:
    def __init__(
        self,
        payload,
        status_code=200,
    ):
        self._payload = payload
        self.status_code = (
            status_code
        )

    def json(self):
        return self._payload


class FakeSession:
    def __init__(
        self,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error
        self.calls = []

    def post(
        self,
        url,
        **kwargs,
    ):
        self.calls.append(
            (
                url,
                kwargs,
            )
        )

        if self.error:
            raise self.error

        return self.response


@pytest.fixture
def oauth_config(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "SCHWAB_CLIENT_ID",
        "test-client-id",
    )

    monkeypatch.setattr(
        config,
        "SCHWAB_CLIENT_SECRET",
        "test-client-secret",
    )

    monkeypatch.setattr(
        config,
        "SCHWAB_REDIRECT_URI",
        "https://example.test/callback",
    )


def test_build_authorization_url(
    oauth_config,
):
    url = (
        service.build_authorization_url(
            "state-123"
        )
    )

    parsed = urlparse(url)

    assert (
        parsed.scheme
        == "https"
    )

    assert (
        parsed.netloc
        == "api.schwabapi.com"
    )

    assert (
        parsed.path
        == "/v1/oauth/authorize"
    )

    query = parse_qs(
        parsed.query
    )

    assert query == {
        "response_type": ["code"],
        "client_id": [
            "test-client-id"
        ],
        "redirect_uri": [
            "https://example.test/callback"
        ],
        "state": [
            "state-123"
        ],
    }


def test_authorization_url_requires_state(
    oauth_config,
):
    with pytest.raises(
        service.SchwabOAuthError,
        match="OAuth state is required",
    ):
        service.build_authorization_url(
            ""
        )


def test_exchange_authorization_code(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token":
                "access-123",
            "refresh_token":
                "refresh-123",
            "expires_in":
                1800,
            "token_type":
                "Bearer",
            "scope":
                "api",
        })
    )

    result = (
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )
    )

    assert result == {
        "access_token":
            "access-123",
        "refresh_token":
            "refresh-123",
        "expires_in":
            1800,
        "token_type":
            "Bearer",
        "scope":
            "api",
    }

    assert len(
        session.calls
    ) == 1

    url, kwargs = (
        session.calls[0]
    )

    assert (
        url
        == service.SCHWAB_TOKEN_URL
    )

    assert kwargs["auth"] == (
        "test-client-id",
        "test-client-secret",
    )

    assert kwargs["data"] == {
        "grant_type":
            "authorization_code",
        "code":
            "code-123",
        "redirect_uri":
            "https://example.test/callback",
    }

    assert (
        kwargs["timeout"]
        == service.DEFAULT_TIMEOUT_SECONDS
    )


def test_refresh_access_token_preserves_refresh_token(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token":
                "new-access",
            "expires_in":
                1800,
            "token_type":
                "Bearer",
        })
    )

    result = (
        service.refresh_access_token(
            "existing-refresh",
            session=session,
        )
    )

    assert (
        result["access_token"]
        == "new-access"
    )

    assert (
        result["refresh_token"]
        == "existing-refresh"
    )

    _, kwargs = (
        session.calls[0]
    )

    assert kwargs["data"] == {
        "grant_type":
            "refresh_token",
        "refresh_token":
            "existing-refresh",
    }


def test_refresh_accepts_rotated_refresh_token(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token":
                "new-access",
            "refresh_token":
                "rotated-refresh",
            "expires_in":
                1800,
        })
    )

    result = (
        service.refresh_access_token(
            "old-refresh",
            session=session,
        )
    )

    assert (
        result["refresh_token"]
        == "rotated-refresh"
    )


def test_token_response_requires_access_token(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "refresh_token":
                "refresh-123",
            "expires_in":
                1800,
        })
    )

    with pytest.raises(
        service.SchwabOAuthError,
        match="access token",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )


def test_initial_exchange_requires_refresh_token(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token":
                "access-123",
            "expires_in":
                1800,
        })
    )

    with pytest.raises(
        service.SchwabOAuthError,
        match="refresh token",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )


def test_invalid_expires_in_is_rejected(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token":
                "access-123",
            "refresh_token":
                "refresh-123",
            "expires_in":
                "not-a-number",
        })
    )

    with pytest.raises(
        service.SchwabOAuthError,
        match="invalid access-token lifetime",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )


def test_http_error_is_fail_closed(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse(
            {
                "error":
                    "invalid_grant",
            },
            status_code=400,
        )
    )

    with pytest.raises(
        service.SchwabOAuthError,
        match="HTTP 400",
    ):
        service.exchange_authorization_code(
            "bad-code",
            session=session,
        )


def test_network_error_is_fail_closed(
    oauth_config,
):
    session = FakeSession(
        error=(
            requests.ConnectionError(
                "offline"
            )
        )
    )

    with pytest.raises(
        service.SchwabOAuthError,
        match="request failed",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )
