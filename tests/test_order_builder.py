from bxk_app.services.order_builder import (
    build_order,
)


def test_build_iron_condor_order():
    trade = {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "expiration": "2026-08-03",
        "credit": 3.05,
        "max_risk": 2195,
        "max_profit": 305,
        "sell_put": 7415,
        "buy_put": 7390,
        "sell_call": 7565,
        "buy_call": 7590,
        "sell_put_symbol":
            "SPXW  260803P07415000",
        "buy_put_symbol":
            "SPXW  260803P07390000",
        "sell_call_symbol":
            "SPXW  260803C07565000",
        "buy_call_symbol":
            "SPXW  260803C07590000",
    }

    order = build_order(
        trade,
        quantity=1,
    )

    assert order["strategy"] == (
        "SPX Iron Condor"
    )

    assert order["symbol"] == "SPX"
    assert order["quantity"] == 1
    assert order["order_type"] == "LIMIT"
    assert order["time_in_force"] == "DAY"
    assert order["limit_price"] == 3.05
    assert order["max_risk"] == 2195
    assert order["max_profit"] == 305

    assert len(order["legs"]) == 4

    assert order["legs"][0] == {
        "action": "SELL",
        "option_type": "PUT",
        "strike": 7415,
        "symbol":
            "SPXW  260803P07415000",
    }

    assert order["legs"][1] == {
        "action": "BUY",
        "option_type": "PUT",
        "strike": 7390,
        "symbol":
            "SPXW  260803P07390000",
    }

    assert order["legs"][2] == {
        "action": "SELL",
        "option_type": "CALL",
        "strike": 7565,
        "symbol":
            "SPXW  260803C07565000",
    }

    assert order["legs"][3] == {
        "action": "BUY",
        "option_type": "CALL",
        "strike": 7590,
        "symbol":
            "SPXW  260803C07590000",
    }


def test_build_order_requires_trade():
    try:
        build_order(
            None,
            quantity=1,
        )

    except ValueError as error:
        assert str(error) == (
            "No trade supplied."
        )

    else:
        raise AssertionError(
            "Expected ValueError"
        )