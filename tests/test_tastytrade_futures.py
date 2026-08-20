from bxk_app.brokers.tastytrade import (
    TastytradeBroker,
)


CONTRACTS = [
    {
        "symbol": "/ESM7",
        "active": True,
        "active-month": False,
    },
    {
        "symbol": "/ESU6",
        "active": True,
        "active-month": True,
    },
    {
        "symbol": "/ESZ6",
        "active": True,
        "active-month": False,
        "next-active-month": True,
    },
]


def test_get_active_future_selects_active_month(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        broker,
        "get_future_instruments",
        lambda product_code: CONTRACTS,
    )

    result = broker.get_active_future("ES")

    assert result is not None
    assert result["symbol"] == "/ESU6"
    assert result["active-month"] is True


def test_get_active_future_fails_closed_without_active_month(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        broker,
        "get_future_instruments",
        lambda product_code: [
            {
                "symbol": "/ESZ6",
                "active": True,
                "active-month": False,
            }
        ],
    )

    result = broker.get_active_future("ES")

    assert result is None
    assert (
        "No active-month future found"
        in broker.last_error
    )


def test_get_future_quote_uses_future_market_data(
    monkeypatch,
):
    broker = TastytradeBroker()

    captured = {}

    def fake_market_data(
        instrument_type,
        symbols,
    ):
        captured["instrument_type"] = (
            instrument_type
        )
        captured["symbols"] = symbols

        return [
            {
                "symbol": "/ESU6",
                "bid": "7696.0",
                "ask": "7696.25",
            }
        ]

    monkeypatch.setattr(
        broker,
        "get_market_data_by_type",
        fake_market_data,
    )

    result = broker.get_future_quote(
        "/ESU6"
    )

    assert (
        captured["instrument_type"]
        == "future"
    )

    assert captured["symbols"] == [
        "/ESU6"
    ]

    assert result["symbol"] == "/ESU6"


def test_get_future_quote_rejects_empty_symbol():
    broker = TastytradeBroker()

    result = broker.get_future_quote("")

    assert result is None
    assert (
        broker.last_error
        == "Future symbol is required."
    )
