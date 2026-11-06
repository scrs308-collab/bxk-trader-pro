"""Read-only broker fill normalization and conservative FIFO contract matching."""
from types import SimpleNamespace

import bxk_app.routes.trade_journal as route
from bxk_app.services.broker_performance_reconciliation import (
    leg_weighted_price, reconcile_contract_fills,
)


SYMBOL = "SPXW  261106C07450000"


def order(order_id, action, price, quantity=1, *, time="2026-11-05T15:00:00Z"):
    return {
        "id": order_id,
        "status": "Filled",
        "price": "99.00",  # original submitted limit MUST NOT become fill
        "legs": [{
            "symbol": SYMBOL, "action": action, "quantity": str(quantity),
            "fills": [{"fill-price": str(price), "quantity": str(quantity), "filled-at": time}],
        }],
    }


def test_actual_fill_price_does_not_use_order_limit():
    leg = order("a", "Buy to Open", "4.25")["legs"][0]
    assert leg_weighted_price(leg, "a") == "4.25"
    assert leg_weighted_price({"quantity": 1, "fills": []}, "a") is None


def test_weighted_partial_fills():
    leg = {"symbol": SYMBOL, "action": "Buy to Open", "quantity": "3",
           "fills": [
               {"fill-price": "1.5", "quantity": "2", "filled-at": "2026-11-05T15:00:00Z"},
               {"fill-price": "3", "quantity": "1", "filled-at": "2026-11-05T15:00:01Z"},
           ]}
    assert leg_weighted_price(leg, "x") == "2.0"


def test_incomplete_broker_fills_do_not_create_estimated_price():
    leg = {"symbol": SYMBOL, "action": "Sell to Close", "quantity": "2",
           "fills": [{"fill-price": "4.50", "quantity": "1",
                      "filled-at": "2026-11-05T15:00:00Z"}]}
    assert leg_weighted_price(leg, "x") is None


def test_fifo_partial_close_and_no_fabricated_net_pnl():
    orders = [
        order("open1", "Buy to Open", "4", quantity=2, time="2026-11-05T14:00:00Z"),
        order("close1", "Sell to Close", "5", quantity=1, time="2026-11-05T15:00:00Z"),
        order("close2", "Sell to Close", "3", quantity=1, time="2026-11-05T16:00:00Z"),
    ]
    result = reconcile_contract_fills(orders)
    assert result["count"] == 2
    assert [r["gross_estimate"] for r in result["matches"]] == ["-100.00", "100.00"]
    assert result["matches"][0]["net_pnl"] is None
    assert result["matches"][0]["fees"] is None
    assert result["unpaired_closing_quantity"] == 0
    assert result["remaining_open_quantity"] == 0


def test_missing_open_and_expiry_not_inferred():
    orders = [order("close", "Sell to Close", "4")]
    result = reconcile_contract_fills(orders)
    assert result["count"] == 0
    assert result["unpaired_closing_quantity"] == 1


def test_invalid_and_nonstandard_instruments_ignored():
    opened = order("a", "Buy to Open", "4")
    opened["legs"][0]["symbol"] = "BAD CONTRACT"
    result = reconcile_contract_fills([opened, order("b", "Sell to Close", "5")])
    assert result["count"] == 0
    assert result["ignored_fill_records"] == 1
    assert result["unpaired_closing_quantity"] == 1


def test_duplicate_orders_do_not_duplicate_fifo_matches():
    opening = order("a", "Buy to Open", "4")
    closing = order("b", "Sell to Close", "5", time="2026-11-05T15:05:00Z")
    result = reconcile_contract_fills([opening, opening, closing])
    assert result["count"] == 1


def test_route_returns_missing_price_as_unknown_not_order_limit(monkeypatch):
    orders = [order("a", "Buy to Open", "4")]
    orders[0]["legs"][0]["fills"] = []
    monkeypatch.setattr(route, "resolve_broker", lambda session, user_context: SimpleNamespace(
        get_first_account_number=lambda: "MOCK",
        get_orders=lambda **kwargs: orders, last_error=None))
    result = route.broker_trade_history(days=30, user_context={"role": "OWNER"}, session=None)
    assert result["count"] == 1
    assert result["orders"][0]["price"] is None
    assert result["orders"][0]["legs"][0]["fill_price"] is None
    assert result["contract_reconciliation"]["count"] == 0
