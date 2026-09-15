from bxk_app.brokers.tastytrade import (
    TASTYTRADE_USER_AGENT,
    TastytradeBroker,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.post_calls = []
        self.request_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(
            payload={"access_token": "test-access-token"}
        )

    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        return FakeResponse(payload={"data": {}})


def test_tastytrade_token_request_sends_user_agent():
    broker = TastytradeBroker(
        client_secret="secret",
        refresh_token="refresh",
        base_url="https://api.example.test",
    )
    fake = FakeSession()
    broker.session = fake

    assert broker.authenticate(force=True) is True

    assert len(fake.post_calls) == 1
    _, kwargs = fake.post_calls[0]

    assert kwargs["headers"]["User-Agent"] == (
        TASTYTRADE_USER_AGENT
    )


def test_tastytrade_api_request_sends_user_agent():
    broker = TastytradeBroker(
        client_secret="secret",
        refresh_token="refresh",
        base_url="https://api.example.test",
    )
    fake = FakeSession()
    broker.session = fake
    broker.access_token = "already-valid"

    response = broker._request(
        "GET",
        "/customers/me/accounts",
    )

    assert response is not None
    assert len(fake.request_calls) == 1

    _, _, kwargs = fake.request_calls[0]

    assert kwargs["headers"]["User-Agent"] == (
        TASTYTRADE_USER_AGENT
    )
