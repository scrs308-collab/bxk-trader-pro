"""Read-only SPXW market-data adapter for the isolated staging app.

Only GET requests to tastytrade OAuth, option-chain and market-data APIs.
Never imports the trading app, database, broker account or order modules.
"""
import os
import threading
import time

import requests
from fastapi import HTTPException

BASE = "https://api.tastyworks.com"
_lock = threading.Lock()
_token = None
_token_expiry = 0.0


def _headers():
    global _token, _token_expiry
    if not (os.getenv("TASTYTRADE_CLIENT_SECRET") and os.getenv("TASTYTRADE_REFRESH_TOKEN")):
        raise HTTPException(503, "Tastytrade market-data credentials are not configured in staging")
    with _lock:
        if not _token or time.time() >= _token_expiry:
            try:
                response = requests.post(
                    BASE + "/oauth/token",
                    json={"grant_type": "refresh_token",
                          "refresh_token": os.environ["TASTYTRADE_REFRESH_TOKEN"],
                          "client_secret": os.environ["TASTYTRADE_CLIENT_SECRET"]},
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                token = payload.get("access_token") or payload.get("data", {}).get("access-token")
                if not token:
                    raise ValueError("No access token returned")
                _token = token
                _token_expiry = time.time() + 12 * 60
            except (requests.RequestException, ValueError, KeyError):
                raise HTTPException(503, "Tastytrade authentication unavailable") from None
        return {"Authorization": "Bearer " + _token, "Accept": "application/json"}


def _get(path, params=None):
    try:
        response = requests.get(BASE + path, params=params, headers=_headers(), timeout=20)
        response.raise_for_status()
        return response.json().get("data", {})
    except (requests.RequestException, ValueError):
        raise HTTPException(503, "Tastytrade market data unavailable") from None


def _spxw():
    data = _get("/option-chains/SPX/nested")
    for item in data.get("items", []):
        if str(item.get("root-symbol", "")).upper() == "SPXW":
            return item
    raise HTTPException(503, "SPXW chain unavailable; standard SPX not substituted")


def get_expirations():
    item = _spxw()
    return {
        "root": "SPXW", "source": "tastytrade",
        "expirations": [
            {"date": row.get("expiration-date"), "dte": row.get("days-to-expiration"),
             "strike_count": len(row.get("strikes", []))}
            for row in item.get("expirations", []) if row.get("expiration-date")
        ],
        "quotes_available": True, "order_execution_enabled": False,
    }


def get_quotes(expiration, min_strike, max_strike):
    if max_strike <= min_strike or max_strike - min_strike > 400:
        raise HTTPException(400, "Strike range must be positive and no greater than 400 points")
    item = _spxw()
    selected = next((x for x in item.get("expirations", [])
                     if x.get("expiration-date") == expiration), None)
    if selected is None:
        raise HTTPException(404, "SPXW expiration not listed")
    contracts = []
    for row in selected.get("strikes", []):
        try:
            strike = float(row["strike-price"])
        except (KeyError, ValueError, TypeError):
            continue
        if min_strike <= strike <= max_strike:
            for kind, field in (("put", "put-streamer-symbol"), ("call", "call-streamer-symbol")):
                symbol = row.get(field)
                if symbol:
                    contracts.append((str(symbol), kind, strike))
    if len(contracts) > 160:
        raise HTTPException(400, "Too many contracts; narrow strike range")
    if not contracts:
        return {"root": "SPXW", "expiration": expiration, "quotes": [],
                "received_quotes": 0, "requested_contracts": 0, "order_execution_enabled": False}
    # Existing BXK quote route uses equity-option. This may require a different
    # instrument type for SPXW; do not fabricate prices when quotes are absent.
    data = _get("/market-data/by-type", {"equity-option": ",".join(x[0] for x in contracts)})
    items = data.get("items", [])
    by_symbol = {str(q.get("symbol") or q.get("instrument-symbol") or ""): q for q in items}
    quotes = []
    for symbol, kind, strike in contracts:
        q = by_symbol.get(symbol)
        if not q:
            continue
        try:
            bid_raw = q.get("bid") if q.get("bid") is not None else q.get("bid-price")
            ask_raw = q.get("ask") if q.get("ask") is not None else q.get("ask-price")
            bid, ask = float(bid_raw), float(ask_raw)
        except (TypeError, ValueError):
            continue
        if not (0 <= bid <= ask):
            continue
        quotes.append({"type": kind, "strike": strike, "bid": bid, "ask": ask,
                       "symbol": symbol, "timestamp": q.get("timestamp") or q.get("quote-time")})
    return {"root": "SPXW", "expiration": expiration, "source": "tastytrade",
            "quotes": quotes, "received_quotes": len(quotes),
            "requested_contracts": len(contracts), "order_execution_enabled": False}
