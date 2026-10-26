"""Strictly bounded tastytrade dry-run adapter. Never submits an order."""
import os
import re
import requests
from fastapi import HTTPException
from staging_market_data import _headers, BASE

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
        response.raise_for_status()
        data = response.json().get("data", {})
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "Tastytrade broker dry-run unavailable") from None
    effect = data.get("buying-power-effect") or {}
    order = data.get("order") or {}
    status = order.get("status") or data.get("status") or "Unknown"
    def numeric(value):
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None
    broker_impact = numeric(effect.get("change-in-buying-power"))
    estimated_risk = round((width - payload.limit_price) * 100, 2)
    delta = round(abs(broker_impact) - estimated_risk, 2) if broker_impact is not None else None
    return {
        "dry_run_only": True,
        "submitted": False,
        "broker_status": status,
        "status_verified": str(status).lower() == "received",
        "warnings": data.get("warnings", []),
        "errors": data.get("errors", []),
        "buying_power_effect": effect,
        "estimated_defined_risk": estimated_risk,
        "broker_buying_power_change": broker_impact,
        "difference_from_defined_risk": delta,
        "reconciled": delta is not None and abs(delta) <= 0.01,
        "execution_authorized": False,
    }
