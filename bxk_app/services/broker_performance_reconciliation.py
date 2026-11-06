"""Read-only option execution normalization and conservative FIFO reconciliation.

Only actual per-leg fills are used: order limit prices are never treated as
execution prices. Contract P/L is a gross estimate, not complete strategy P/L.
"""
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

STANDARD_OCC = re.compile(r"^[A-Z0-9.]{1,6} *[0-9]{6}[CP][0-9]{8}$")
OPEN_ACTIONS = {"BUY TO OPEN": "LONG", "SELL TO OPEN": "SHORT"}
CLOSE_ACTIONS = {"SELL TO CLOSE": "LONG", "BUY TO CLOSE": "SHORT"}


def decimal_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    return result if result.is_finite() else None


def valid_timestamp(value):
    try:
        if not isinstance(value, str):
            return None
        value = value.strip().replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            return None
        return timestamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_leg_fills(leg, order_id):
    """Return actual execution lots; no estimate if fill data is incomplete."""
    if not isinstance(leg, dict):
        return []
    fills = leg.get("fills")
    if not isinstance(fills, list) or not fills:
        return []
    symbol = str(leg.get("symbol") or "").strip().upper()
    action = " ".join(str(leg.get("action") or "").upper().split())
    records = []
    for index, fill in enumerate(fills):
        if not isinstance(fill, dict):
            return []
        price = decimal_value(fill.get("fill-price"))
        if price is None:
            price = decimal_value(fill.get("price"))
        quantity = decimal_value(fill.get("quantity"))
        if quantity is None and len(fills) == 1:
            quantity = decimal_value(leg.get("quantity"))
        timestamp = valid_timestamp(fill.get("filled-at"))
        if (price is None or price < 0 or quantity is None or quantity <= 0
                or quantity != quantity.to_integral_value() or timestamp is None):
            return []
        records.append({
            "symbol": symbol, "action": action, "quantity": int(quantity),
            "price": price, "timestamp": timestamp,
            "order_id": order_id, "fill_index": index,
        })
    return records


def extract_option_fills(orders):
    executions = []
    for order in orders:
        if not isinstance(order, dict) or str(order.get("status") or "").strip().lower() != "filled":
            continue
        order_id = str(order.get("id") or "").strip()
        for leg in order.get("legs") or []:
            executions.extend(parse_leg_fills(leg, order_id))
    return executions


def leg_weighted_price(leg, order_id):
    """Weighted per-contract fill, or None when broker fill detail is incomplete."""
    lots = parse_leg_fills(leg, order_id)
    if not lots:
        return None
    total = sum((x["quantity"] for x in lots), 0)
    expected = decimal_value(leg.get("quantity"))
    if expected is not None and expected != total:
        return None
    return str(sum((x["price"] * x["quantity"] for x in lots), Decimal(0)) / total)


def reconcile_contract_fills(orders):
    """FIFO by option symbol and long/short side, no invented trade-level P/L.

    All results are *gross estimates*. 100x multiplier is restricted to
    standard OCC equity-option symbols; expiration, exercise, and assignment
    are not reconstructed and may leave unmatched lots.
    """
    fills = extract_option_fills(orders)
    fills.sort(key=lambda x: (x["timestamp"], x["order_id"], x["fill_index"]))
    books = defaultdict(deque)
    matches = []
    unpaired_closing_quantity = 0
    ignored = 0
    seen = set()
    for fill in fills:
        symbol, action = fill["symbol"], fill["action"]
        if not STANDARD_OCC.fullmatch(symbol) or action not in OPEN_ACTIONS and action not in CLOSE_ACTIONS:
            ignored += 1
            continue
        key = (fill["order_id"], symbol, action, fill["fill_index"])
        if key in seen:
            continue
        seen.add(key)
        if action in OPEN_ACTIONS:
            side = OPEN_ACTIONS[action]
            books[(symbol, side)].append({**fill, "remaining": fill["quantity"]})
            continue
        side = CLOSE_ACTIONS[action]
        remaining = fill["quantity"]
        queue = books[(symbol, side)]
        while remaining and queue:
            opening = queue[0]
            quantity = min(remaining, opening["remaining"])
            factor = Decimal(1) if side == "LONG" else Decimal(-1)
            gross = (fill["price"] - opening["price"]) * factor * quantity * 100
            matches.append({
                "symbol": symbol, "side": side, "quantity": quantity,
                "open_order_id": opening["order_id"], "close_order_id": fill["order_id"],
                "opened_at": opening["timestamp"].isoformat(),
                "closed_at": fill["timestamp"].isoformat(),
                "entry_fill": str(opening["price"]),
                "exit_fill": str(fill["price"]),
                "gross_estimate": str(gross.quantize(Decimal("0.01"))),
                "fees": None, "net_pnl": None,
            })
            opening["remaining"] -= quantity
            remaining -= quantity
            if opening["remaining"] == 0:
                queue.popleft()
        unpaired_closing_quantity += remaining

    matches.sort(key=lambda x: x["closed_at"], reverse=True)
    return {
        "matches": matches,
        "count": len(matches),
        "unpaired_closing_quantity": unpaired_closing_quantity,
        "remaining_open_quantity": sum(lot["remaining"] for queue in books.values() for lot in queue),
        "ignored_fill_records": ignored,
        "label": "Contract FIFO gross estimates — not strategy P/L",
        "disclaimer": "Matches only actual fills for the same standard OCC contract within the requested history window. Missing earlier openings, expiration, assignments, cash settlement, adjusted contracts, and broker fees are not reconciled; net P/L is not calculated.",
    }
