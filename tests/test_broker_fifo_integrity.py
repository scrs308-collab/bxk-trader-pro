"""Prevent incomplete fills and repeated FIFO fragments from inflating performance."""

from bxk_app.services.broker_performance_reconciliation import (
    extract_option_fills,
    reconcile_contract_fills,
)

SYM = "SPXW  261106C07450000"
T0 = "2026-11-05T14:00:00Z"
T1 = "2026-11-05T15:00:00Z"


def leg(action, qty, fills):
    return {
        "symbol": SYM,
        "action": action,
        "quantity": str(qty),
        "fills": [
            {"fill-price": str(price), "quantity": str(amount), "filled-at": time}
            for price, amount, time in fills
        ],
    }


def order(oid, *legs):
    return {"id": oid, "status": "Filled", "legs": list(legs)}


def test_incomplete_open_or_close_excluded_from_fifo():
    incomplete_open = order("o1", leg("Buy to Open", 2, [(4, 1, T0)]))
    close = order("c1", leg("Sell to Close", 1, [(5, 1, T1)]))
    result = reconcile_contract_fills([incomplete_open, close])
    assert result["count"] == 0
    assert result["unpaired_closing_quantity"] == 1

    open_order = order("o2", leg("Buy to Open", 1, [(4, 1, T0)]))
    incomplete_close = order("c2", leg("Sell to Close", 2, [(5, 1, T1)]))
    result = reconcile_contract_fills([open_order, incomplete_close])
    assert result["count"] == 0
    assert result["remaining_open_quantity"] == 1


def test_duplicate_broker_orders_are_deduplicated():
    opened = order("o1", leg("Buy to Open", 1, [(4, 1, T0)]))
    closed = order("c1", leg("Sell to Close", 1, [(5, 1, T1)]))
    result = reconcile_contract_fills([opened, opened, closed, closed])
    assert result["count"] == 1
    assert result["matches"][0]["gross_estimate"] == "100.00"


def test_same_order_multiple_leg_indices_are_not_collapsed():
    opened = order(
        "o1",
        leg("Buy to Open", 1, [(4, 1, T0)]),
        leg("Buy to Open", 1, [(4, 1, T0)]),
    )
    extracted = extract_option_fills([opened])
    assert len(extracted) == 2
    assert {x["leg_index"] for x in extracted} == {0, 1}


def test_identical_fifo_fragments_are_consolidated_with_quantity_and_dollars():
    opened = order("o1", leg("Buy to Open", 3, [
        (4, 1, T0), (4, 1, T0), (4, 1, T0),
    ]))
    closed = order("c1", leg("Sell to Close", 3, [
        (5, 1, T1), (5, 1, T1), (5, 1, T1),
    ]))
    result = reconcile_contract_fills([opened, closed])
    assert result["count"] == 1
    match = result["matches"][0]
    assert match["quantity"] == 3
    assert match["gross_estimate"] == "300.00"
    assert match["net_pnl"] is None
    assert result["remaining_open_quantity"] == 0
    assert result["unpaired_closing_quantity"] == 0
