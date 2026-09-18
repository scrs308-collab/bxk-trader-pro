import pytest

from bxk_app.brokers.base import (
    BrokerBase,
)
from bxk_app.brokers.schwab import (
    SchwabBroker,
)
from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
)


class MinimalBroker(
    BrokerBase
):
    broker_name = "minimal"

    def authenticate(self):
        return True

    def get_status(self):
        return {}

    def get_accounts(self):
        return []

    def get_balances(
        self,
        account_number=None,
    ):
        return {}

    def get_positions(
        self,
        account_number=None,
    ):
        return []

    def get_quote(
        self,
        symbol: str,
    ):
        return {}


def test_base_summary_methods_are_optional_but_fail_closed():
    broker = MinimalBroker()

    with pytest.raises(
        NotImplementedError,
        match="normalized account summary",
    ):
        broker.get_account_summary()

    with pytest.raises(
        NotImplementedError,
        match="normalized position summaries",
    ):
        broker.get_position_summary()


def test_schwab_normalizes_long_option_position(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="token",
        account_number="11111111",
    )

    monkeypatch.setattr(
        broker,
        "get_positions",
        lambda account_number=None: [
            {
                "longQuantity": 1,
                "shortQuantity": 0,
                "averagePrice": 2.25,
                "marketValue": 175.0,
                "currentDayProfitLoss":
                    -20.0,
                "instrument": {
                    "symbol":
                        "SPXW  260911P06400000",
                    "assetType":
                        "OPTION",
                },
            }
        ],
    )

    result = (
        broker.get_position_summary()
    )

    assert len(result) == 1

    leg = result[0]

    assert (
        leg["symbol"]
        == "SPXW  260911P06400000"
    )

    assert leg["direction"] == "LONG"
    assert leg["quantity"] == 1.0

    assert (
        leg["average_open_price"]
        == 2.25
    )

    assert leg["close_price"] == 1.75
    assert leg["multiplier"] == 100.0
    assert leg["day_pnl"] == -20.0


def test_schwab_normalizes_short_option_position(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="token",
        account_number="11111111",
    )

    monkeypatch.setattr(
        broker,
        "get_positions",
        lambda account_number=None: [
            {
                "longQuantity": 0,
                "shortQuantity": 2,
                "averagePrice": 1.80,
                "marketValue": -300.0,
                "instrument": {
                    "symbol":
                        "SPXW  260911C06600000",
                    "assetType":
                        "OPTION",
                },
            }
        ],
    )

    result = (
        broker.get_position_summary()
    )

    assert len(result) == 1

    leg = result[0]

    assert leg["direction"] == "SHORT"
    assert leg["quantity"] == 2.0
    assert leg["close_price"] == 1.5
    assert leg["cost_effect"] == "Credit"


def test_schwab_ignores_flat_position(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="token",
        account_number="11111111",
    )

    monkeypatch.setattr(
        broker,
        "get_positions",
        lambda account_number=None: [
            {
                "longQuantity": 1,
                "shortQuantity": 1,
                "instrument": {
                    "symbol":
                        "SPXW  260911P06400000",
                    "assetType":
                        "OPTION",
                },
            }
        ],
    )

    assert (
        broker.get_position_summary()
        == []
    )


def test_schwab_normalizes_account_summary(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="token",
        account_number="11111111",
    )

    monkeypatch.setattr(
        broker,
        "get_balances",
        lambda account_number=None: {
            "cashBalance":
                1234.56,
            "liquidationValue":
                25000.25,
            "availableFunds":
                9000.0,
            "buyingPower":
                18000.0,
            "maintenanceRequirement":
                3500.0,
            "equity":
                24500.0,
        },
    )

    monkeypatch.setattr(
        broker,
        "get_position_summary",
        lambda: [
            {"symbol": "ONE"},
            {"symbol": "TWO"},
        ],
    )

    monkeypatch.setattr(
        broker,
        "get_default_account_number",
        lambda: "11111111",
    )

    result = (
        broker.get_account_summary()
    )

    assert result == {
        "number":
            "11111111",
        "net_liquidation":
            25000.25,
        "cash":
            1234.56,
        "buying_power":
            18000.0,
        "derivative_buying_power":
            18000.0,
        "maintenance":
            3500.0,
        "margin_equity":
            24500.0,
        "open_positions":
            2,
    }


def test_schwab_account_summary_returns_none_without_balances(
    monkeypatch,
):
    broker = SchwabBroker(
        access_token="token",
        account_number="11111111",
    )

    monkeypatch.setattr(
        broker,
        "get_balances",
        lambda account_number=None: {},
    )

    assert (
        broker.get_account_summary()
        is None
    )


def test_tastytrade_position_summary_adds_live_option_quote(
    monkeypatch,
):
    broker = TastytradeBroker(
        client_secret="secret",
        refresh_token="refresh",
        account_number="5WT00000",
        base_url="https://example.test",
    )

    monkeypatch.setattr(
        broker,
        "get_positions",
        lambda account_number=None: [
            {
                "symbol":
                    "SPXW  260921P07570000",
                "streamer-symbol":
                    ".SPXW260921P7570",
                "underlying-symbol": "SPX",
                "instrument-type":
                    "Equity Option",
                "quantity": "1",
                "quantity-direction": "SHORT",
                "average-open-price": "4.00",
                "close-price": "0",
                "cost-effect": "Credit",
                "expires-at":
                    "2026-09-21T20:00:00.000Z",
                "multiplier": "100",
            }
        ],
    )

    captured = {}

    def fake_quotes(symbols):
        captured["symbols"] = symbols
        return [
            {
                "symbol":
                    "SPXW  260921P07570000",
                "bid": "1.10",
                "ask": "1.30",
            }
        ]

    monkeypatch.setattr(
        broker,
        "get_option_quotes",
        fake_quotes,
    )

    result = broker.get_position_summary()

    assert captured["symbols"] == [
        "SPXW  260921P07570000"
    ]
    assert len(result) == 1
    assert result[0]["bid"] == 1.1
    assert result[0]["ask"] == 1.3
    assert result[0]["current_price"] == 1.2
    assert result[0]["price_source"] == "live-mid"
    assert result[0]["pnl"] == 280.0


def test_tastytrade_option_quotes_use_authenticated_market_data(
    monkeypatch,
):
    broker = TastytradeBroker()
    captured = {}

    class Response:
        def json(self):
            return {
                "data": {
                    "items": [
                        {
                            "symbol": "OPTION",
                            "bid": "1.00",
                            "ask": "1.10",
                        }
                    ]
                }
            }

    def fake_request(
        method,
        path,
        *,
        params=None,
        json_body=None,
    ):
        captured.update({
            "method": method,
            "path": path,
            "params": params,
        })
        return Response()

    monkeypatch.setattr(
        broker,
        "_request",
        fake_request,
    )

    result = broker.get_option_quotes(
        ["OPTION"]
    )

    assert result[0]["bid"] == "1.00"
    assert captured == {
        "method": "GET",
        "path": "/market-data/by-type",
        "params": {
            "equity-option": "OPTION",
        },
    }
