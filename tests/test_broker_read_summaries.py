import pytest

from bxk_app.brokers.base import (
    BrokerBase,
)
from bxk_app.brokers.schwab import (
    SchwabBroker,
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
