import pytest

from bxk_app.brokers.schwab import (
    SchwabBroker,
)


def test_schwab_declares_read_only_capabilities():
    broker = SchwabBroker()

    assert broker.broker_name == "schwab"
    assert broker.supports("accounts") is True
    assert broker.supports("balances") is True
    assert broker.supports("positions") is True

    assert (
        broker.supports("order_preview")
        is False
    )

    assert (
        broker.supports("order_submission")
        is False
    )

    with pytest.raises(
        NotImplementedError
    ):
        broker.preview_order({})


def test_authentication_fails_without_token():
    broker = SchwabBroker()

    assert broker.authenticate() is False

    assert (
        broker.last_error
        == "Schwab access token is unavailable."
    )


def test_get_accounts_normalizes_schwab_mapping(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="test-token"
    )

    monkeypatch.setattr(
        broker,
        "_request",
        lambda *args, **kwargs: [
            {
                "accountNumber": "11111111",
                "hashValue": "HASH111",
            }
        ],
    )

    accounts = broker.get_accounts()

    assert accounts == [
        {
            "account_number": "11111111",
            "broker_account_key": "HASH111",
        }
    ]

    assert (
        broker.get_default_account_number()
        == "11111111"
    )


def test_multiple_accounts_require_default(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="test-token"
    )

    monkeypatch.setattr(
        broker,
        "_request",
        lambda *args, **kwargs: [
            {
                "accountNumber": "11111111",
                "hashValue": "HASH111",
            },
            {
                "accountNumber": "22222222",
                "hashValue": "HASH222",
            },
        ],
    )

    assert (
        broker.get_default_account_number()
        is None
    )

    assert (
        "select a default account"
        in broker.last_error
    )


def test_configured_default_account_is_used(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="test-token",
        account_number="22222222",
    )

    monkeypatch.setattr(
        broker,
        "_request",
        lambda *args, **kwargs: [
            {
                "accountNumber": "11111111",
                "hashValue": "HASH111",
            },
            {
                "accountNumber": "22222222",
                "hashValue": "HASH222",
            },
        ],
    )

    assert (
        broker.get_default_account_number()
        == "22222222"
    )


def test_balances_use_schwab_account_hash(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="test-token",
        account_number="11111111",
    )

    broker._accounts_cache = [
        {
            "account_number": "11111111",
            "broker_account_key": "HASH111",
        }
    ]

    captured = {}

    def fake_request(
        method,
        path,
        *,
        params=None,
    ):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = params

        return {
            "securitiesAccount": {
                "currentBalances": {
                    "cashBalance": 1234.56,
                }
            }
        }

    monkeypatch.setattr(
        broker,
        "_request",
        fake_request,
    )

    balances = broker.get_balances()

    assert balances == {
        "cashBalance": 1234.56,
    }

    assert captured["method"] == "GET"

    assert (
        captured["path"]
        == (
            "/trader/v1/accounts/"
            "HASH111"
        )
    )


def test_positions_use_schwab_account_hash(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="test-token",
        account_number="11111111",
    )

    broker._accounts_cache = [
        {
            "account_number": "11111111",
            "broker_account_key": "HASH111",
        }
    ]

    captured = {}

    def fake_request(
        method,
        path,
        *,
        params=None,
    ):
        captured["path"] = path
        captured["params"] = params

        return {
            "securitiesAccount": {
                "positions": [
                    {
                        "longQuantity": 1,
                    }
                ]
            }
        }

    monkeypatch.setattr(
        broker,
        "_request",
        fake_request,
    )

    positions = broker.get_positions()

    assert positions == [
        {
            "longQuantity": 1,
        }
    ]

    assert (
        captured["path"]
        == (
            "/trader/v1/accounts/"
            "HASH111"
        )
    )

    assert captured["params"] == {
        "fields": "positions",
    }


def test_schwab_quote_is_not_broker_capability():
    broker = SchwabBroker(
        access_token="test-token"
    )

    assert broker.supports("quotes") is False

    with pytest.raises(
        NotImplementedError,
        match="market-data provider",
    ):
        broker.get_quote("SPX")
