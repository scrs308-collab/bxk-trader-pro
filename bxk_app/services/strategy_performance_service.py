"""Conservative read-only strategy reconciliation for broker-confirmed option orders.

A verified net result requires a UNIQUE opening strategy, exact reversed
closing legs and complete broker transaction cash flows for every order.
Ambiguous/repeated strategies, rolls, unsupported settlement activity, and
historical opening trades are never assigned fabricated realized P/L.
"""
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from bxk_app.services import trade_journal_service as journal_service
from decimal import Decimal
from itertools import chain
import re

from bxk_app.services.broker_performance_reconciliation import (
    decimal_value, parse_leg_fills, valid_timestamp,
)

OCC = re.compile(r"^([A-Z0-9.]{1,6})\s*(\d{6})([CP])(\d{8})$")
OPEN = {"BUY TO OPEN": "LONG", "SELL TO OPEN": "SHORT"}
CLOSE = {"SELL TO CLOSE": "LONG", "BUY TO CLOSE": "SHORT"}
CENT = Decimal("0.01")
MULTIPLIER = Decimal(100)
EXCHANGE_TZ = ZoneInfo("America/New_York")


def _money(value):
    return str(value.quantize(CENT)) if value is not None else None


def _signed_transaction(value, effect):
    number = decimal_value(value)
    direction = str(effect or "").strip().upper()
    if number == 0 and direction == "NONE":
        return Decimal(0)
    if number is None or direction not in {"CREDIT", "DEBIT"}:
        return None
    return abs(number) * (1 if direction == "CREDIT" else -1)


def _option_symbol(value):
    symbol = str(value or "").strip().upper()
    match = OCC.fullmatch(symbol)
    if match:
        return f"{match[1]:6}{match[2]}{match[3]}{match[4]}"
    return symbol


def _ledger_cash(row):
    """Return finalized gross and net ledger cash, with fees independently checked."""
    if row.get("is-estimated-fee") is not False:
        return "ESTIMATED_FEES" if row.get("is-estimated-fee") is True else "UNVERIFIED_FEES", None, None
    if row.get("reverses-id") or row.get("currency", "USD") != "USD":
        return "INVALID_TRANSACTION", None, None
    gross = _signed_transaction(row.get("value"), row.get("value-effect"))
    net = _signed_transaction(row.get("net-value"), row.get("net-value-effect"))
    if gross is None or net is None:
        return "INVALID_TRANSACTION", None, None
    fees = Decimal(0)
    for name in (
        "commission", "clearing-fees", "regulatory-fees", "currency-conversion-fees",
        "proprietary-index-option-fees", "other-charge",
    ):
        raw = row.get(name)
        if raw is None:
            continue
        direction = str(row.get(name + "-effect") or "").strip().upper()
        amount = decimal_value(raw)
        if amount == 0 and direction in {"", "NONE"}:
            continue
        if amount is None or amount < 0 or direction not in {"DEBIT", "CREDIT"}:
            return "INVALID_FEE_DETAIL", None, None
        fees += amount * (1 if direction == "DEBIT" else -1)
    if (gross - net).quantize(CENT) != fees.quantize(CENT):
        return "UNVERIFIED_FEES", None, None
    return "VERIFIED", gross, net


def _order_record(order):
    if not isinstance(order, dict) or str(order.get("status") or "").upper() != "FILLED":
        return None
    order_id = str(order.get("id") or "").strip()
    legs = order.get("legs")
    if not order_id or not isinstance(legs, list) or len(legs) not in {1, 2, 4}:
        return None
    phase = None
    parsed = []
    fill_times = []
    for leg in legs:
        if not isinstance(leg, dict):
            return None
        action = " ".join(str(leg.get("action") or "").upper().split())
        current = "OPEN" if action in OPEN else "CLOSE" if action in CLOSE else None
        if current is None or phase is not None and current != phase:
            return None
        phase = current
        symbol = _option_symbol(leg.get("symbol"))
        match = OCC.fullmatch(symbol)
        quantity = decimal_value(leg.get("quantity"))
        fills = parse_leg_fills(leg, order_id)
        if not match or quantity is None or not fills:
            return None
        fill_times.extend(fill["timestamp"] for fill in fills)
        cash = sum((fill["price"] * fill["quantity"] for fill in fills), Decimal(0)) * MULTIPLIER
        side = (OPEN if phase == "OPEN" else CLOSE)[action]
        parsed.append({
            "symbol": symbol, "side": side, "action": action,
            "quantity": int(quantity), "gross": cash if action.startswith("SELL") else -cash,
            "expiry": match.group(2),
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
    try:
        expiration = datetime.strptime(parsed[0]["expiry"], "%y%m%d").date()
    except ValueError:
        return None
    if max(fill_times).astimezone(EXCHANGE_TZ).date() > expiration:
        return None
    gross = sum((leg["gross"] for leg in parsed), Decimal(0))
    signature = tuple(sorted((leg["symbol"], leg["side"]) for leg in parsed))
    return {
        "id": order_id, "phase": phase, "time": min(fill_times), "last_fill": max(fill_times), "expiration": expiration,
        "quantity": parsed[0]["quantity"], "signature": signature,
        "legs": parsed, "gross_per_contract": gross / parsed[0]["quantity"],
        "gross_total": gross,
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
    gross_by_leg = defaultdict(Decimal)
    net = Decimal(0)
    seen = {}
    for row in relevant:
        identifier = str(row.get("id") or "").strip()
        if not identifier or (identifier in seen and row != seen[identifier]):
            return {"status": "DUPLICATE_OR_MISSING_TRANSACTION_ID", "net": None}
        if identifier in seen:
            continue
        seen[identifier] = row
        symbol = _option_symbol(row.get("symbol"))
        action = " ".join(str(row.get("action") or "").upper().split())
        quantity = decimal_value(row.get("quantity"))
        if ((symbol, action) not in expected or quantity is None
                or quantity <= 0 or quantity != quantity.to_integral_value()):
            return {"status": "INVALID_TRANSACTION", "net": None}
        status, gross_value, net_value = _ledger_cash(row)
        if status != "VERIFIED":
            return {"status": status, "net": None}
        received[(symbol, action)] += int(quantity)
        gross_by_leg[(symbol, action)] += gross_value
        net += net_value
    if dict(received) != expected or any(
        gross_by_leg[(leg["symbol"], leg["action"])].quantize(CENT) != leg["gross"].quantize(CENT)
        for leg in order["legs"]
    ):
        return {"status": "TRANSACTION_MISMATCH", "net": None}
    if any(isinstance(row, dict) and str(row.get("reverses-id")) in seen for row in transactions):
        return {"status": "REVERSED_TRANSACTION", "net": None}
    gross = sum(gross_by_leg.values(), Decimal(0))
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


def _settlement_candidate(opening, transactions, other_openings):
    """Reuse the established complete SPXW settlement evidence validator.

    Never allocate transaction evidence across repeated/overlapping openings.
    Verify net separately against finalized entry and terminal ledger cash.
    """
    if len(opening["legs"]) != 4:
        return None
    if any(leg["root"] != "SPXW" for leg in opening["legs"]):
        return None
    symbols = {leg["symbol"] for leg in opening["legs"]}
    if any(
        other["id"] != opening["id"]
        and symbols.intersection(leg["symbol"] for leg in other["legs"])
        for other in other_openings
    ):
        return None
    expiration = opening["expiration"]
    if expiration > datetime.now(EXCHANGE_TZ).date():
        return None
    snapshot = {
        "order": {
            "legs": [
                {"symbol": leg["symbol"], "quantity": leg["quantity"]}
                for leg in opening["legs"]
            ]
        }
    }
    journal = SimpleNamespace(
        expiration=expiration,
        quantity=opening["quantity"],
        entry_snapshot=snapshot,
    )
    normalized = [
        {**row, "symbol": _option_symbol(row.get("symbol"))}
        for row in transactions if isinstance(row, dict)
    ]
    evidence = journal_service._expiration_settlement_evidence(journal, normalized)
    if not evidence.get("complete"):
        return None
    terminal = evidence["transactions"]
    if any(
        (timestamp := valid_timestamp(row.get("executed-at"))) is None
        or timestamp <= opening["last_fill"]
        or timestamp > datetime.now(timezone.utc)
        or row.get("reverses-id")
        or (str(row.get("transaction-sub-type")).strip().upper() == "EXPIRATION"
            and decimal_value(row.get("value")) != 0)
        for row in terminal
    ):
        return None
    settlement_debit = decimal_value(evidence.get("settlement_dollars"))
    if settlement_debit is None:
        return None
    gross = opening["gross_total"] - settlement_debit
    entry = _transaction_money(opening, transactions)
    terminal_cash = [_ledger_cash(row) for row in terminal]
    terminal_ids = [row.get("id") for row in terminal]
    terminal_id_set = {str(identifier) for identifier in terminal_ids}
    # A conflicting duplicate can be collapsed by the journal's gross validator.
    ledger_rows = [row for row in normalized if str(row.get("id")) in terminal_id_set]
    companions = [
        row for row in normalized
        if row["symbol"] in symbols
        and journal_service._transaction_date(row) == expiration
        and str(row.get("transaction-sub-type") or "").strip().upper() in {"ASSIGNMENT", "EXERCISE"}
    ]
    final = (
        entry["status"] == "VERIFIED"
        and all(terminal_ids)
        and len(terminal_id_set) == len(terminal_ids)
        and all(row in terminal for row in ledger_rows)
        and not any(str(row.get("reverses-id")) in terminal_id_set for row in normalized)
        and all(_ledger_cash(row) == ("VERIFIED", Decimal(0), Decimal(0)) for row in companions)
        and all(status == "VERIFIED" for status, _, _ in terminal_cash)
        and sum((value for _, value, _ in terminal_cash), Decimal(0)) == -settlement_debit
    )
    net = entry["net"] + sum((value for _, _, value in terminal_cash), Decimal(0)) if final else None
    return {
        "gross": gross,
        "net": net,
        "closed_at": evidence["closed_at"].isoformat(),
        "resolution": (
            "CASH_SETTLEMENT_GROSS_VERIFIED"
            if evidence["cash_settled"]
            else "EXPIRED_WORTHLESS_GROSS_VERIFIED"
        ),
    }


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
    all_openings = list(chain.from_iterable(opening_groups.values()))
    unmatched_closes = 0
    for signature, group in opening_groups.items():
        related = closings.pop(signature, [])
        # Never choose an arbitrary opening when the exact same strategy
        # was traded more than once in the period.
        if len(group) != 1:
            # Repeated openings cannot be allocated safely, but their
            # closing quantities must still appear in unmatched diagnostics.
            unmatched_closes += sum(c["quantity"] for c in related)
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
            if closing["time"] <= opening["last_fill"] or closing["quantity"] > available:
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
        settlement = None
        if not related and transactions_available:
            settlement = _settlement_candidate(opening, transactions, all_openings)
        if settlement is not None:
            status = settlement["resolution"]
            gross = settlement["gross"]
            net = settlement["net"]
            if net is not None:
                fees = gross - net
            review = (
                "All four expiration legs have broker terminal evidence; "
                "gross settlement cash flow verified. Entry/settlement fees "
                "and final net P/L remain unverified."
            ) if net is None else "Entry and terminal cash flows verified against finalized broker transactions."
        settlement_events = [
            tx for tx in transactions
            if isinstance(tx, dict)
            and str(tx.get("transaction-sub-type") or "").strip().upper()
            in {"EXPIRATION", "ASSIGNMENT", "EXERCISE", *journal_service._SETTLEMENT_SUBTYPES}
            and _option_symbol(tx.get("symbol"))
            in {leg["symbol"] for leg in opening["legs"]}
        ]
        if settlement_events and settlement is None:
            review = "Settlement, exercise or assignment activity requires separate verification."
        overlaps = closed and any(
            order["id"] != opening["id"]
            and order["time"] <= max(close["last_fill"] for close in applicable)
            and set(order["signature"]).intersection(opening["signature"])
            for order in all_openings
        )
        if overlaps:
            review = "Another opening shares the same contracts and sides; trade linkage requires review."
        if closed and not available and not overlaps and transactions_available and not settlement_events:
            order_finances = [_transaction_money(item, transactions) for item in [opening, *applicable]]
            if all(item["status"] == "VERIFIED" for item in order_finances):
                net = sum((item["net"] for item in order_finances), Decimal(0))
                gross = sum((item["gross"] for item in order_finances), Decimal(0))
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
            "closed_at": max(order["last_fill"] for order in applicable).isoformat() if applicable else (
                settlement["closed_at"] if settlement else None
            ),
            "quantity": opening["quantity"],
            "closed_quantity": opening["quantity"] if settlement else closed,
            "open_quantity": 0 if settlement else available,
            "gross_estimate": _money(gross) if (closed or settlement) else None,
            "fees": _money(fees), "net_pnl": _money(net),
            "reason": review,
        })
        unmatched_closes += sum(
            c["quantity"] for c in related if c not in applicable
        )
    unmatched_closes += sum(c["quantity"] for items in closings.values() for c in items)
    rows.sort(key=lambda r: r.get("closed_at") or r.get("opened_at") or "", reverse=True)
    verified = [Decimal(row["net_pnl"]) for row in rows if row["net_pnl"] is not None]
    return {
        "records": rows[:limit],
        "total_candidates": len(rows),
        "verified_count": len(verified),
        "settlement_gross_count": sum(
            r["status"] in {
                "CASH_SETTLEMENT_GROSS_VERIFIED",
                "EXPIRED_WORTHLESS_GROSS_VERIFIED",
            } for r in rows
        ),
        "estimated_fee_transaction_count": sum(
            row.get("is-estimated-fee") is True
            for row in transactions if isinstance(row, dict)
        ),
        "partial_count": sum(r["status"] == "PARTIAL_CLOSE" for r in rows),
        "ambiguous_count": sum(r["status"] == "AMBIGUOUS_REPEAT" for r in rows),
        "unmatched_closing_contracts": max(unmatched_closes, 0),
        "unsupported_orders": unsupported,
        "net_pnl_total": None,
        "verified_net_subtotal": _money(sum(verified)) if verified else None,
        "warning": "Read-only strategy review. Net P/L requires complete broker cash flows and finalized fees. Repeated structures, partial positions, assignments, and out-of-window trades remain unverified.",
    }
