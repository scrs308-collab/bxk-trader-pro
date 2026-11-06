"""Conservative read-only strategy reconciliation for broker-confirmed option orders.

A verified net result requires a UNIQUE opening strategy, exact reversed
closing legs and complete broker transaction cash flows for every order.
Ambiguous/repeated strategies, rolls, unsupported settlement activity, and
historical opening trades are never assigned fabricated realized P/L.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import chain
import re

from bxk_app.services.broker_performance_reconciliation import (
    decimal_value, leg_weighted_price, valid_timestamp,
)

OCC = re.compile(r"^([A-Z0-9.]{1,6})\\s*(\\d{6})([CP])(\\d{8})$")
OPEN = {"BUY TO OPEN": "LONG", "SELL TO OPEN": "SHORT"}
CLOSE = {"SELL TO CLOSE": "LONG", "BUY TO CLOSE": "SHORT"}
CENT = Decimal("0.01")
MULTIPLIER = Decimal(100)


def _money(value):
    return str(value.quantize(CENT)) if value is not None else None


def _signed_transaction(value, effect):
    number = decimal_value(value)
    direction = str(effect or "").strip().upper()
    if number is None or direction not in {"CREDIT", "DEBIT"}:
        return None
    return abs(number) * (1 if direction == "CREDIT" else -1)


def _order_time(order):
    timestamps = []
    for leg in order.get("legs") or []:
        for fill in leg.get("fills") or []:
            if isinstance(fill, dict):
                time = valid_timestamp(fill.get("filled-at"))
                if time:
                    timestamps.append(time)
    if not timestamps:
        return None
    return min(timestamps)


def _order_record(order):
    if not isinstance(order, dict) or str(order.get("status") or "").upper() != "FILLED":
        return None
    order_id = str(order.get("id") or "").strip()
    legs = order.get("legs")
    if not order_id or not isinstance(legs, list) or len(legs) not in {1, 2, 4}:
        return None
    phase = None
    parsed = []
    for leg in legs:
        if not isinstance(leg, dict):
            return None
        action = " ".join(str(leg.get("action") or "").upper().split())
        current = "OPEN" if action in OPEN else "CLOSE" if action in CLOSE else None
        if current is None or phase is not None and current != phase:
            return None
        phase = current
        symbol = str(leg.get("symbol") or "").strip().upper()
        match = OCC.fullmatch(symbol)
        quantity = decimal_value(leg.get("quantity"))
        price = decimal_value(leg_weighted_price(leg, order_id))
        if not match or quantity is None or quantity <= 0 or quantity != quantity.to_integral_value() or price is None:
            return None
        side = (OPEN if phase == "OPEN" else CLOSE)[action]
        parsed.append({
            "symbol": symbol, "side": side, "action": action,
            "quantity": int(quantity), "price": price, "expiry": match.group(2),
            "root": match.group(1), "type": match.group(3),
            "strike": int(match.group(4)), "sell": action.startswith("SELL"),
        })
    if len({leg["quantity"] for leg in parsed}) != 1:
        return None
    if len({leg["expiry"] for leg in parsed}) != 1 or len({leg["root"] for leg in parsed}) != 1:
        return None
    symbols = [leg["symbol"] for leg in parsed]
    if len(set(symbols)) != len(symbols):
        return None
    timestamp = _order_time(order)
    if timestamp is None:
        return None
    gross_per_contract = sum(
        (leg["price"] * (1 if leg["sell"] else -1) for leg in parsed),
        Decimal(0),
    ) * MULTIPLIER
    signature = tuple(sorted((leg["symbol"], leg["side"]) for leg in parsed))
    return {
        "id": order_id, "phase": phase, "time": timestamp,
        "quantity": parsed[0]["quantity"], "signature": signature,
        "legs": parsed, "gross_per_contract": gross_per_contract,
        "gross_total": gross_per_contract * parsed[0]["quantity"],
    }


def _transaction_money(order, transactions):
    """Verify trade transactions belong to every leg and reconcile gross cash."""
    relevant = [
        row for row in transactions
        if isinstance(row, dict) and str(row.get("order-id") or "").strip() == order["id"]
        and str(row.get("transaction-type") or "").strip().upper() == "TRADE"
    ]
    if not relevant:
        return {"status": "MISSING_TRANSACTIONS", "net": None}
    expected = {(leg["symbol"], leg["action"]): leg["quantity"] for leg in order["legs"]}
    received = defaultdict(int)
    gross = Decimal(0)
    net = Decimal(0)
    seen = set()
    for row in relevant:
        if row.get("is-estimated-fee") is True:
            return {"status": "ESTIMATED_FEES", "net": None}
        identifier = str(row.get("id") or "").strip()
        if not identifier or identifier in seen:
            return {"status": "DUPLICATE_OR_MISSING_TRANSACTION_ID", "net": None}
        seen.add(identifier)
        symbol = str(row.get("symbol") or "").strip().upper()
        action = " ".join(str(row.get("action") or "").upper().split())
        quantity = decimal_value(row.get("quantity"))
        gross_value = _signed_transaction(row.get("value"), row.get("value-effect"))
        net_value = _signed_transaction(row.get("net-value"), row.get("net-value-effect"))
        if ((symbol, action) not in expected or quantity is None
                or quantity <= 0 or quantity != quantity.to_integral_value()
                or gross_value is None or net_value is None):
            return {"status": "INVALID_TRANSACTION", "net": None}
        received[(symbol, action)] += int(quantity)
        gross += gross_value
        net += net_value
    if dict(received) != expected or abs(gross - order["gross_total"]) > Decimal("0.05"):
        return {"status": "TRANSACTION_MISMATCH", "net": None}
    return {
        "status": "VERIFIED", "gross": gross, "net": net,
        "fees": gross - net,
    }


def _strategy_label(order):
    legs = order["legs"]
    if len(legs) == 1:
        return "Single option"
    if len(legs) == 2:
        return "Two-leg option strategy"
    types = sorted(leg["type"] for leg in legs)
    if types == ["C", "C", "P", "P"]:
        return "Four-leg condor structure"
    return "Four-leg option strategy"


def reconcile_strategies(orders, transactions=None, *, transactions_available=True, limit=100):
    """Return conservative candidate strategy pairs and unsupported/unmatched counts."""
    transactions = transactions if isinstance(transactions, list) else []
    seen_orders = set()
    parsed = []
    unsupported = 0
    for raw in orders or []:
        if not isinstance(raw, dict):
            unsupported += 1
            continue
        identifier = str(raw.get("id") or "").strip()
        if not identifier or identifier in seen_orders:
            continue
        seen_orders.add(identifier)
        record = _order_record(raw)
        if record is None:
            unsupported += 1
        else:
            parsed.append(record)

    opening_groups = defaultdict(list)
    closings = defaultdict(list)
    for record in parsed:
        (opening_groups if record["phase"] == "OPEN" else closings)[record["signature"]].append(record)
    for group in chain(opening_groups.values(), closings.values()):
        group.sort(key=lambda row: (row["time"], row["id"]))

    rows = []
    unmatched_closes = 0
    for signature, group in opening_groups.items():
        related = closings.pop(signature, [])
        # Never choose an arbitrary opening when the exact same strategy
        # was traded more than once in the period.
        if len(group) != 1:
            rows.append({
                "status": "AMBIGUOUS_REPEAT", "strategy": _strategy_label(group[0]),
                "opening_orders": [r["id"] for r in group],
                "closing_orders": [r["id"] for r in related],
                "quantity": sum(x["quantity"] for x in group),
                "net_pnl": None, "gross_estimate": None,
                "reason": "Repeated identical structure; trade linkage is ambiguous.",
            })
            continue
        opening = group[0]
        available = opening["quantity"]
        applicable = []
        for closing in related:
            if closing["time"] <= opening["time"] or closing["quantity"] > available:
                unmatched_closes += closing["quantity"]
                continue
            available -= closing["quantity"]
            applicable.append(closing)
        closed = opening["quantity"] - available
        # gross difference is the actual cash flows of opening portion
        # plus corresponding closing orders, without fees.
        gross = opening["gross_per_contract"] * closed + sum(
            (c["gross_total"] for c in applicable), Decimal(0)
        )
        status = (
            "OPEN_OR_MISSING_CLOSE" if closed == 0 else
            "PARTIAL_CLOSE" if available else "GROSS_ONLY"
        )
        net = None
        fees = None
        review = "Closing order missing or expired/assigned position is not reconciled."
        if closed:
            review = "Partial closure; unclosed contracts and settlements require review." if available else "Fill-matched; fees or brokerage transactions incomplete."
        if closed and not available and transactions_available:
            order_finances = [_transaction_money(item, transactions) for item in [opening, *applicable]]
            if all(item["status"] == "VERIFIED" for item in order_finances):
                net = sum((item["net"] for item in order_finances), Decimal(0))
                fees = gross - net
                status = "TRANSACTION_VERIFIED"
                review = "Net order cash flows verified against broker trade transactions; independent assignments or settlement outside these orders not included."
            else:
                review = "Missing or unmatched broker transaction evidence: " + ", ".join(item["status"] for item in order_finances)
        rows.append({
            "status": status, "strategy": _strategy_label(opening),
            "opening_orders": [opening["id"]],
            "closing_orders": [x["id"] for x in applicable],
            "opened_at": opening["time"].isoformat(),
            "closed_at": applicable[-1]["time"].isoformat() if applicable else None,
            "quantity": opening["quantity"], "closed_quantity": closed,
            "open_quantity": available,
            "gross_estimate": _money(gross) if closed else None,
            "fees": _money(fees), "net_pnl": _money(net),
            "reason": review,
        })
        unmatched_closes += sum(
            c["quantity"] for c in related if c not in applicable
        ) - sum(c["quantity"] for c in related if c["time"] <= opening["time"] or c["quantity"] > opening["quantity"])
    unmatched_closes += sum(c["quantity"] for items in closings.values() for c in items)
    rows.sort(key=lambda r: r.get("closed_at") or r.get("opened_at") or "", reverse=True)
    return {
        "records": rows[:limit],
        "total_candidates": len(rows),
        "verified_count": sum(r["status"] == "TRANSACTION_VERIFIED" for r in rows),
        "partial_count": sum(r["status"] == "PARTIAL_CLOSE" for r in rows),
        "ambiguous_count": sum(r["status"] == "AMBIGUOUS_REPEAT" for r in rows),
        "unmatched_closing_contracts": max(unmatched_closes, 0),
        "unsupported_orders": unsupported,
        "net_pnl_total": None,
        "warning": "Read-only candidate strategy reconciliation. No global P/L: rolling, repeat structures, partial/unmatched positions, expiration, cash settlement, assignments, and out-of-window orders require further verification.",
    }
