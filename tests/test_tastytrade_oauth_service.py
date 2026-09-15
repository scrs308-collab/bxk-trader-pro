from urllib.parse import parse_qs, urlparse

import pytest
import requests

from bxk_app import config
from bxk_app.services import tastytrade_oauth_service as service


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))

        if self.error:
            raise self.error

        return self.response


@pytest.fixture
def oauth_config(monkeypatch):
    monkeypatch.setattr(
        config,
        "TASTYTRADE_CLIENT_ID",
        "test-client-id",
    )
    monkeypatch.setattr(
        config,
        "TASTYTRADE_CLIENT_SECRET",
        "test-client-secret",
    )
    monkeypatch.setattr(
        config,
        "TASTYTRADE_REDIRECT_URI",
        "https://example.test/callback",
    )


def test_build_authorization_url(oauth_config):
    url = service.build_authorization_url("state-123")

    parsed = urlparse(url)

    assert parsed.scheme == "https"
    assert parsed.netloc == "my.tastytrade.com"
    assert parsed.path == "/auth.html"

    query = parse_qs(parsed.query)

    assert query == {
        "client_id": ["test-client-id"],
        "redirect_uri": [
            "https://example.test/callback"
        ],
        "response_type": ["code"],
        "scope": ["read trade openid"],
        "state": ["state-123"],
    }


def test_authorization_url_requires_state(oauth_config):
    with pytest.raises(
        service.TastytradeOAuthError,
        match="OAuth state is required",
    ):
        service.build_authorization_url("")


def test_exchange_authorization_code(oauth_config):
    session = FakeSession(
        response=FakeResponse({
            "access_token": "access-123",
            "refresh_token": "refresh-123",
            "expires_in": 900,
            "token_type": "Bearer",
            "scope": "read trade openid",
            "id_token": "id-123",
        })
    )

    result = service.exchange_authorization_code(
        "code-123",
        session=session,
    )

    assert result == {
        "access_token": "access-123",
        "refresh_token": "refresh-123",
        "expires_in": 900,
        "token_type": "Bearer",
        "scope": "read trade openid",
        "id_token": "id-123",
    }

    assert len(session.calls) == 1

    url, kwargs = session.calls[0]

    assert url == service.TASTYTRADE_TOKEN_URL

    assert kwargs["headers"] == {
        "User-Agent": service.TASTYTRADE_USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    assert kwargs["json"] == {
        "grant_type": "authorization_code",
        "code": "code-123",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "redirect_uri": "https://example.test/callback",
    }


def test_initial_exchange_requires_refresh_token(
    oauth_config,
):
    session = FakeSession(
        response=FakeResponse({
            "access_token": "access-123",
            "expires_in": 900,
        })
    )

    with pytest.raises(
        service.TastytradeOAuthError,
        match="refresh token",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )


def test_http_error_fails_closed(oauth_config):
    session = FakeSession(
        response=FakeResponse(
            {"error": "invalid_grant"},
            status_code=400,
        )
    )

    with pytest.raises(
        service.TastytradeOAuthError,
        match="HTTP 400",
    ):
        service.exchange_authorization_code(
            "bad-code",
            session=session,
        )


def test_network_error_fails_closed(oauth_config):
    session = FakeSession(
        error=requests.ConnectionError("offline")
    )

    with pytest.raises(
        service.TastytradeOAuthError,
        match="request failed",
    ):
        service.exchange_authorization_code(
            "code-123",
            session=session,
        )
