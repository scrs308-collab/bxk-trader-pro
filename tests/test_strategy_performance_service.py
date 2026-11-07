"""Conservative strategy-level broker reconciliation: never fabricate net P/L."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from bxk_app.services.strategy_performance_service import reconcile_strategies
import bxk_app.routes.trade_journal as route

EXPIRES = "261106"
SYMBOLS = [
    "SPXW  261106C07500000", "SPXW  261106C07510000",
    "SPXW  261106P07345000", "SPXW  261106P07335000",
]
OPEN_ACTIONS = ["Sell to Open", "Buy to Open", "Sell to Open", "Buy to Open"]
CLOSE_ACTIONS = ["Buy to Close", "Sell to Close", "Buy to Close", "Sell to Close"]
OPEN_PRICES = ["6.68", "5.31", "6.54", "5.51"]
CLOSE_PRICES = ["0.32", "0.27", "2.07", "1.52"]


def make_order(oid, closing=False, qty=4, *, at=None):
    if at is None:
        at = "2026-11-06T17:30:00Z" if closing else "2026-11-06T14:00:00Z"
    actions = CLOSE_ACTIONS if closing else OPEN_ACTIONS
    prices = CLOSE_PRICES if closing else OPEN_PRICES
    return {
        "id": oid, "status": "Filled",
        "legs": [{
            "symbol": symbol, "action": action, "quantity": str(qty),
            "fills": [{"fill-price": price, "quantity": str(qty), "filled-at": at}],
        } for symbol, action, price in zip(SYMBOLS, actions, prices)],
    }


def make_transactions(order):
    result = []
    for i, leg in enumerate(order["legs"]):
        price = Decimal(leg["fills"][0]["fill-price"])
        quantity = int(leg["quantity"])
        value = price * quantity * 100
        direction = "Credit" if leg["action"].startswith("Sell") else "Debit"
        net_value = value - Decimal("0.25") if direction == "Credit" else value + Decimal("0.25")
        result.append({
            "id": str(order["id"]) + "-" + str(i),
            "order-id": order["id"],
            "transaction-type": "Trade",
            "action": leg["action"],
            "symbol": leg["symbol"],
            "quantity": str(quantity),
            "value": str(value), "value-effect": direction,
            "net-value": str(net_value), "net-value-effect": direction,
            "commission": "0.25", "commission-effect": "Debit",
            "is-estimated-fee": False,
        })
    return result


def test_exact_four_leg_credit_strategy_with_verified_transaction_fees():
    op = make_order("open")
    cl = make_order("close", closing=True)
    transactions = make_transactions(op) + make_transactions(cl)
    out = reconcile_strategies([cl, op], transactions)
    row = out["records"][0]
    assert row["status"] == "TRANSACTION_VERIFIED"
    assert row["quantity"] == 4
    assert row["closed_quantity"] == 4
    assert row["gross_estimate"] == "720.00"
    assert row["fees"] == "2.00"
    assert row["net_pnl"] == "718.00"
    assert out["verified_count"] == 1
    assert out["net_pnl_total"] is None


def test_absent_transactions_never_produce_net():
    out = reconcile_strategies([make_order("a"), make_order("b", closing=True)],
                               transactions_available=False)
    row = out["records"][0]
    assert row["status"] == "GROSS_ONLY"
    assert row["gross_estimate"] == "720.00"
    assert row["net_pnl"] is None
    assert row["fees"] is None


def test_partial_close_is_labeled_and_never_net():
    out = reconcile_strategies([make_order("a", qty=4), make_order("b", closing=True, qty=2)])
    row = out["records"][0]
    assert row["status"] == "PARTIAL_CLOSE"
    assert row["closed_quantity"] == 2
    assert row["open_quantity"] == 2
    assert row["gross_estimate"] == "360.00"
    assert row["net_pnl"] is None


def test_repeated_identical_strategy_is_ambiguous():
    orders = [make_order("a"), make_order("b", at="2026-11-06T14:05:00Z"), make_order("c", closing=True)]
    out = reconcile_strategies(orders)
    row = out["records"][0]
    assert row["status"] == "AMBIGUOUS_REPEAT"
    assert row["net_pnl"] is None
    assert out["ambiguous_count"] == 1


def test_closes_without_open_remain_unmatched():
    out = reconcile_strategies([make_order("c", closing=True)])
    assert out["records"] == []
    assert out["unmatched_closing_contracts"] == 4


def test_mixed_open_close_roll_is_not_reconciled():
    order = make_order("r")
    order["legs"][0]["action"] = "Buy to Close"
    out = reconcile_strategies([order])
    assert out["unsupported_orders"] == 1
    assert out["verified_count"] == 0


def test_fee_mismatch_prevents_verified_net():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    tx[0]["value"] = "999"
    out = reconcile_strategies([op, cl], tx)
    row = out["records"][0]
    assert row["status"] == "GROSS_ONLY"
    assert row["net_pnl"] is None
    assert "UNVERIFIED_FEES" in row["reason"]


def test_fee_components_must_reconcile_to_broker_net_cash():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    tx[0].pop("commission")
    tx[0].pop("commission-effect")
    out = reconcile_strategies([op, cl], tx)
    assert out["records"][0]["net_pnl"] is None
    assert "UNVERIFIED_FEES" in out["records"][0]["reason"]


def test_assignment_or_expiration_blocks_verified_net():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    tx.append({
        "transaction-type": "Receive Deliver",
        "transaction-sub-type": "Assignment",
        "symbol": SYMBOLS[0],
    })
    out = reconcile_strategies([op, cl], tx)
    assert out["records"][0]["net_pnl"] is None
    assert "Settlement" in out["records"][0]["reason"]


def test_estimated_fees_prevent_verified_net():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    tx[0]["is-estimated-fee"] = True
    out = reconcile_strategies([op, cl], tx)
    assert out["records"][0]["net_pnl"] is None


def test_broker_history_still_loads_when_transaction_endpoint_fails(monkeypatch):
    order = make_order("o")
    class Broker:
        last_error = None
        def get_first_account_number(self):
            return "MOCK"
        def get_orders(self, **kwargs):
            self.last_error = None
            return [order]
        def get_transactions(self, **kwargs):
            self.last_error = "Unavailable"
            return []
    monkeypatch.setattr(route, "resolve_broker", lambda session, user_context: Broker())
    out = route.broker_trade_history(days=30, user_context={"role": "OWNER"}, session=None)
    assert out["count"] == 1
    assert out["strategy_review"]["transaction_notice"]
    assert out["strategy_review"]["verified_count"] == 0


def test_duplicate_order_ids_and_no_invented_expiration_settlement():
    op = make_order("o")
    out = reconcile_strategies([op, op])
    assert out["total_candidates"] == 1
    assert out["records"][0]["status"] == "OPEN_OR_MISSING_CLOSE"
    assert out["records"][0]["net_pnl"] is None


def test_repeated_structure_closes_count_as_unmatched():
    orders = [
        make_order("a"),
        make_order("b", at="2026-11-06T14:05:00Z"),
        make_order("c", closing=True, qty=2),
    ]
    out = reconcile_strategies(orders)
    assert out["ambiguous_count"] == 1
    assert out["unmatched_closing_contracts"] == 2
    assert out["records"][0]["net_pnl"] is None


def test_normalizes_occ_padding_and_ignores_identical_ledger_duplicates():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    for row in tx:
        row["symbol"] = row["symbol"].replace(" ", "")
    result = reconcile_strategies([op, cl], tx + tx)
    assert result["records"][0]["net_pnl"] == "718.00"
    assert result["verified_net_subtotal"] == "718.00"


def test_offsetting_leg_mismatches_cannot_verify_an_order():
    op, cl = make_order("o"), make_order("c", closing=True)
    tx = make_transactions(op) + make_transactions(cl)
    for row in tx[:2]:
        for key in ("value", "net-value"):
            row[key] = str(Decimal(row[key]) + 1)
    row = reconcile_strategies([op, cl], tx)["records"][0]
    assert row["net_pnl"] is None
    assert "TRANSACTION_MISMATCH" in row["reason"]


def test_close_cannot_start_before_opening_order_finishes_filling():
    op, cl = make_order("o"), make_order("c", closing=True)
    op["legs"][-1]["fills"][0]["filled-at"] = "2026-11-06T18:00:00Z"
    result = reconcile_strategies([op, cl], make_transactions(op) + make_transactions(cl))
    assert result["records"][0]["closed_quantity"] == 0
    assert result["unmatched_closing_contracts"] == 4


def test_tastytrade_csv_estimated_fee_fallback_requires_every_fill():
    import csv
    import io
    from bxk_app.services.tastytrade_transaction_csv import COLUMNS, read_transactions_csv

    opening = make_order("100")
    closing = make_order("101", closing=True)
    transactions = make_transactions(opening) + make_transactions(closing)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=sorted(COLUMNS))
    writer.writeheader()
    for tx in transactions:
        tx["is-estimated-fee"] = True
        order = opening if tx["order-id"] == "100" else closing
        gross = Decimal(tx["value"]) * (-1 if tx["value-effect"] == "Debit" else 1)
        writer.writerow({
            "Date": order["legs"][0]["fills"][0]["filled-at"],
            "Type": "Trade", "Action": tx["action"].upper().replace(" ", "_"),
            "Symbol": tx["symbol"], "Instrument Type": "Equity Option",
            "Value": f"{gross:,}", "Quantity": tx["quantity"],
            "Commissions": "-4.00" if order is opening else "0.00", "Fees": "-2.88",
            "Multiplier": "100", "Order #": order["id"], "Currency": "USD",
            "Total": gross - Decimal("2.88") - (4 if order is opening else 0),
        })
    evidence = read_transactions_csv(output.getvalue().encode())
    args = ([opening, closing], transactions)
    result = reconcile_strategies(*args, csv_orders=evidence)
    assert result["verified_count"] == 0
    assert result["csv_reconciled_count"] == 1
    assert result["records"][0]["status"] == "CSV_RECONCILED"
    assert result["records"][0]["net_pnl"] == "680.96"
    assert result["records"][0]["fees"] == "39.04"

    evidence["101"].append(evidence["101"][0])
    duplicate = reconcile_strategies(*args, csv_orders=evidence)
    assert duplicate["records"][0]["net_pnl"] is None

    evidence["101"] = evidence["101"][1:-1]
    partial = reconcile_strategies(*args, csv_orders=evidence)
    assert partial["records"][0]["net_pnl"] is None
    assert "CSV evidence is incomplete" in partial["records"][0]["reason"]


def test_transactions_csv_upload_requires_transactions_export():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[route.require_owner_or_beta] = lambda: {"role": "OWNER"}
    app.dependency_overrides[route.get_db] = lambda: None
    client = TestClient(app)
    url = "/api/trade-journal/broker-history/transactions-csv"
    response = client.post(url, content="Symbol,Status,Price\nSPX,Filled,2.40 cr\n",
                           headers={"Content-Type": "text/csv"})
    assert response.status_code == 422
    assert "Transactions CSV with commissions and fees" in response.json()["detail"]
