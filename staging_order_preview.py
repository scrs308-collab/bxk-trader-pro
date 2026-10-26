"""Strictly bounded tastytrade dry-run adapter. Never submits an order."""
import os
import re
import requests
from datetime import datetime, timezone
from fastapi import HTTPException
from staging_market_data import _headers, BASE, get_quotes

OCC = re.compile(r"^SPXW  [0-9]{6}[PC][0-9]{8}$")


def preview(payload):
    account = os.getenv("TASTYTRADE_ACCOUNT_NUMBER", "").strip()
    if not account or not re.fullmatch(r"[A-Za-z0-9-]{4,40}", account):
        raise HTTPException(503, "Staging tastytrade account number not configured")
    if os.getenv("BXK_PREVIEW_MODE", "").lower() != "true" or os.getenv("BXK_LIVE_TRADING_ENABLED", "").lower() != "false":
        raise HTTPException(403, "Staging safety flags must explicitly disable live trading")
    legs = payload.legs
    if len(legs) != 4 or payload.quantity != 1:
        raise HTTPException(400, "Only one complete four-leg iron condor can be previewed")
    if [x.action for x in legs] != ["Sell to Open", "Buy to Open", "Sell to Open", "Buy to Open"]:
        raise HTTPException(400, "Unexpected leg order")
    if any(not OCC.fullmatch(x.symbol) for x in legs):
        raise HTTPException(400, "Only SPXW OCC symbols are permitted")
    parsed = [(x.symbol[6:12], x.symbol[12], int(x.symbol[13:])/1000) for x in legs]
    if len({x[0] for x in parsed}) != 1 or [x[1] for x in parsed] != ["P","P","C","C"]:
        raise HTTPException(400, "Legs must share expiration and be ordered put/put/call/call")
    if not (parsed[1][2] < parsed[0][2] < parsed[2][2] < parsed[3][2]):
        raise HTTPException(400, "Invalid iron condor strikes")
    width = max(parsed[0][2]-parsed[1][2],parsed[3][2]-parsed[2][2])
    if not 0 < payload.limit_price < width:
        raise HTTPException(400, "Credit must be positive and below maximum wing width")
    # Independently re-fetch all four legs immediately before the broker dry-run.
    # Never trust the browser's freshness label or quoted premium.
    expiry = "20" + parsed[0][0][:2] + "-" + parsed[0][0][2:4] + "-" + parsed[0][0][4:6]
    low = min(x[2] for x in parsed)
    high = max(x[2] for x in parsed)
    snapshot = get_quotes(expiry, max(0.01, low - 1), high + 1)
    quote_index = {q["symbol"]: q for q in snapshot.get("quotes", [])}
    now = datetime.now(timezone.utc)
    fresh_quotes = []
    for leg in legs:
        quote = quote_index.get(leg.symbol)
        if not quote or not quote.get("timestamp"):
            raise HTTPException(409, "Missing fresh broker quote for one or more legs")
        try:
            timestamp = datetime.fromisoformat(quote["timestamp"].replace("Z", "+00:00"))
            age = (now - timestamp).total_seconds()
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(409, "Invalid broker quote timestamp") from None
        if not -60 <= age <= 120:
            raise HTTPException(409, "Broker quote is stale; refresh and review again")
        fresh_quotes.append(quote)
    def mid(q):
        return (float(q["bid"]) + float(q["ask"])) / 2
    current_credit = round(mid(fresh_quotes[0]) - mid(fresh_quotes[1])
                           + mid(fresh_quotes[2]) - mid(fresh_quotes[3]), 2)
    if current_credit <= 0 or abs(current_credit - payload.limit_price) > 0.10:
        raise HTTPException(409, "Quoted premium changed; refresh and select a new position")
    request_payload = {
        "time-in-force": "Day", "order-type": "Limit",
        "price": f"{payload.limit_price:.2f}", "price-effect": "Credit",
        "legs": [{"instrument-type": "Equity Option", "symbol": leg.symbol,
                  "quantity": 1, "action": leg.action} for leg in legs],
    }
    try:
        response = requests.post(
            f"{BASE}/accounts/{account}/orders/dry-run",
            json=request_payload, headers=_headers(), timeout=20,
        )
        if not response.ok:
            # Return a bounded broker HTTP status and safe error codes, never account data.
            try:
                body = response.json()
                errors = body.get("error", {}) if isinstance(body, dict) else {}
                if isinstance(errors, dict):
                    code = errors.get("code") or errors.get("error-code")
                else:
                    code = None
            except ValueError:
                code = None
            safe_code = str(code)[:64] if code and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", str(code)) else "unspecified"
            raise HTTPException(502, {
                "reason": "Broker rejected dry-run request",
                "broker_http_status": response.status_code,
                "broker_error_code": safe_code,
            })
        data = response.json().get("data", {})
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "Tastytrade connection or response unavailable") from None
    effect = data.get("buying-power-effect") or {}
    order = data.get("order") or {}
    fees = data.get("fee-calculation") or {}
    status = order.get("status") or data.get("status") or "Unknown"
    def numeric(value):
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None
    impact = numeric(effect.get("change-in-buying-power"))
    current = numeric(effect.get("current-buying-power"))
    remaining = numeric(effect.get("new-buying-power"))
    fee_total = numeric(fees.get("total-fees"))
    risk = round((width - payload.limit_price) * 100, 2)
    variance = round(impact-risk, 2) if impact is not None else None
    unexplained = round(variance-fee_total, 2) if variance is not None and fee_total is not None else None
    broker_legs = order.get("legs") or []
    legs_match = len(broker_legs) == 4 and all(
        all(actual.get(k) == expected.get(k) for k in ("symbol","action","quantity","instrument-type"))
        for actual, expected in zip(broker_legs, request_payload["legs"])
    )
    price_match = numeric(order.get("price")) == numeric(request_payload["price"])
    order_match = (
        legs_match and price_match and order.get("order-type") == "Limit"
        and order.get("time-in-force") == "Day" and order.get("price-effect") == "Credit"
    )
    bp_internal_match = (
        current is not None and remaining is not None and impact is not None
        and abs(round(current-remaining-impact, 2)) <= 0.01
    )
    reserve = numeric(os.getenv("BXK_MIN_REMAINING_BUYING_POWER", "15000"))
    reserve_ok = remaining is not None and reserve is not None and remaining >= reserve
    warnings = data.get("warnings") or []
    approved_codes = {"tif.next_valid_session"}
    warning_codes = [w.get("code") if isinstance(w, dict) else None for w in warnings]
    warnings_approved = all(code in approved_codes for code in warning_codes)
    errors = data.get("errors") or []
    checks = {
        "broker_status_received": status == "Received",
        "order_matches_request": order_match,
        "broker_buying_power_internal": bp_internal_match,
        "fees_reported": fee_total is not None and fee_total >= 0,
        "risk_plus_fees_matches_impact": unexplained is not None and abs(unexplained) <= 0.05,
        "remaining_buying_power_reserve": reserve_ok,
        "broker_warnings_approved": warnings_approved,
        "broker_errors_absent": len(errors) == 0,
    }
    return {
        "dry_run_only": True, "submitted": False,
        "broker_status": status, "checks": checks,
        "all_checks_pass": all(checks.values()),
        "warnings": warnings, "errors": errors,
        "estimated_defined_risk": risk,
        "broker_buying_power_change": impact,
        "current_buying_power": current, "remaining_buying_power": remaining,
        "minimum_buying_power_reserve": reserve,
        "broker_total_fees": fee_total,
        "difference_from_defined_risk": variance,
        "unexplained_difference_after_fees": unexplained,
        "execution_authorized": False,
        "server_quote_verified": True,
        "server_quote_credit_points": current_credit,
        "server_quote_checked_at": now.isoformat(),
    }
