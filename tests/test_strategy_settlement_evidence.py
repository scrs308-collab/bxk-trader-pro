"""Independent regression coverage for read-only SPXW gross settlement evidence."""
from bxk_app.services.strategy_performance_service import reconcile_strategies

SYMBOLS = [
    "SPXW  261015C07500000",
    "SPXW  261015C07510000",
    "SPXW  261015P07345000",
    "SPXW  261015P07335000",
]
ACTIONS = ["Sell to Open", "Buy to Open", "Sell to Open", "Buy to Open"]
PRICES = ["6.68", "5.31", "6.54", "5.51"]


def entry(order_id="open", quantity=4):
    return {
        "id": order_id, "status": "Filled",
        "legs": [
            {"symbol": sym, "action": action, "quantity": str(quantity),
             "fills": [{"fill-price": price, "quantity": str(quantity),
                        "filled-at": "2026-10-14T14:00:00Z"}]}
            for sym, action, price in zip(SYMBOLS, ACTIONS, PRICES)
        ],
    }


def expiration(symbol, qty=4):
    return {
        "id": "exp-" + symbol[-6:],
        "transaction-type": "Receive Deliver",
        "transaction-sub-type": "Expiration",
        "transaction-date": "2026-10-15",
        "executed-at": "2026-10-15T20:00:00Z",
        "symbol": symbol,
        "quantity": qty,
        "value": "0",
        "value-effect": "None",
    }


def cash(symbol, effect, value, qty=4):
    return {
        "id": "cash-" + symbol[-6:],
        "transaction-type": "Receive Deliver",
        "transaction-sub-type": (
            "Cash Settled Assignment" if effect == "Debit" else
            "Cash Settled Exercise"
        ),
        "transaction-date": "2026-10-15",
        "executed-at": "2026-10-15T21:00:00Z",
        "symbol": symbol,
        "quantity": qty,
        "value": str(value),
        "value-effect": effect,
    }


def test_expiration_all_legs_confirms_gross_not_net():
    result = reconcile_strategies(
        [entry()],
        [expiration(symbol) for symbol in SYMBOLS],
    )
    item = result["records"][0]
    assert item["status"] == "EXPIRED_WORTHLESS_GROSS_VERIFIED"
    assert item["gross_estimate"] == "960.00"
    assert item["fees"] is None and item["net_pnl"] is None
    assert item["closed_quantity"] == 4
    assert item["open_quantity"] == 0
    assert result["settlement_gross_count"] == 1


def test_cash_settlement_uses_broker_cash_values_not_marks():
    transactions = [
        expiration(SYMBOLS[0]), expiration(SYMBOLS[1]),
        cash(SYMBOLS[2], "Debit", 2000),
        cash(SYMBOLS[3], "Credit", 1000),
    ]
    result = reconcile_strategies([entry()], transactions)
    item = result["records"][0]
    assert item["status"] == "CASH_SETTLEMENT_GROSS_VERIFIED"
    assert item["gross_estimate"] == "-40.00"
    assert item["net_pnl"] is None
    assert item["fees"] is None


def test_missing_terminal_leg_does_not_verify_expiration():
    transactions = [expiration(symbol) for symbol in SYMBOLS[:3]]
    item = reconcile_strategies([entry()], transactions)["records"][0]
    assert item["status"] == "OPEN_OR_MISSING_CLOSE"
    assert item["gross_estimate"] is None
    assert item["net_pnl"] is None


def test_repeated_or_overlapping_openings_do_not_claim_same_settlement():
    orders = [entry("one"), entry("two")]
    result = reconcile_strategies(orders, [expiration(symbol) for symbol in SYMBOLS])
    assert result["verified_count"] == 0
    assert result["settlement_gross_count"] == 0
    assert result["records"][0]["status"] == "AMBIGUOUS_REPEAT"


def test_duplicate_cash_settlement_evidence_is_deduplicated():
    rows = [
        expiration(SYMBOLS[0]), expiration(SYMBOLS[1]),
        cash(SYMBOLS[2], "Debit", 2000),
        cash(SYMBOLS[3], "Credit", 1000),
    ]
    result = reconcile_strategies([entry()], rows + rows)
    assert result["records"][0]["status"] == "CASH_SETTLEMENT_GROSS_VERIFIED"
    assert result["records"][0]["gross_estimate"] == "-40.00"


def test_wrong_date_or_quantity_cannot_verify_terminal_evidence():
    rows = [expiration(symbol) for symbol in SYMBOLS]
    rows[0]["transaction-date"] = "2026-10-16"
    result = reconcile_strategies([entry()], rows)
    assert result["settlement_gross_count"] == 0
    rows[0]["transaction-date"] = "2026-10-15"
    rows[0]["quantity"] = 3
    result = reconcile_strategies([entry()], rows)
    assert result["settlement_gross_count"] == 0


def test_estimated_fees_still_block_net_even_with_settlement_evidence():
    rows = [expiration(symbol) for symbol in SYMBOLS]
    rows.append({"id": "tx1", "transaction-type": "Trade", "is-estimated-fee": True})
    result = reconcile_strategies([entry()], rows)
    assert result["estimated_fee_transaction_count"] == 1
    assert result["records"][0]["net_pnl"] is None


def test_settlement_unavailable_never_fabricates_gross():
    result = reconcile_strategies([entry()], transactions_available=False)
    assert result["settlement_gross_count"] == 0
    assert result["records"][0]["gross_estimate"] is None


def test_terminal_net_requires_finalized_entry_and_all_four_terminal_transactions():
    from test_strategy_performance_service import make_transactions

    opening = entry()
    rows = make_transactions(opening)
    terminal = [
        expiration(SYMBOLS[0]), expiration(SYMBOLS[1]),
        cash(SYMBOLS[2], "Debit", 2000), cash(SYMBOLS[3], "Credit", 1000),
    ]
    for row in terminal:
        row.update({
            "is-estimated-fee": False, "net-value": row["value"],
            "net-value-effect": row["value-effect"],
        })
    terminal[2].update({
        "net-value": "2000.50", "other-charge": "0.50", "other-charge-effect": "Debit",
    })
    result = reconcile_strategies([opening], rows + terminal)
    assert result["records"][0]["net_pnl"] == "-41.50"
    assert result["records"][0]["fees"] == "1.50"
    assert result["verified_net_subtotal"] == "-41.50"

    terminal[2]["is-estimated-fee"] = True
    result = reconcile_strategies([opening], rows + terminal)
    assert result["records"][0]["net_pnl"] is None
    assert result["records"][0]["gross_estimate"] == "-40.00"
