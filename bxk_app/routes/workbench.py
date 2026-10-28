"""Authenticated, read-only tastytrade SPXW market-data bridge.

Staging fails closed until BXK authentication and broker credentials are configured.
No order submission or account operations are exposed by this module.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from bxk_app import config
from bxk_app.authorization import require_owner
from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.option_scanner import get_spxw_chain_item

router = APIRouter(prefix="/api/workbench", tags=["Workbench"])

@router.get("/expirations")
def workbench_expirations(user=Depends(require_owner)):
    if not config.BXK_AUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Authenticated workbench required")
    if not (config.TASTYTRADE_CLIENT_SECRET and config.TASTYTRADE_REFRESH_TOKEN):
        raise HTTPException(status_code=503, detail="Tastytrade market-data connection not configured")
    chain = tastytrade_api.get_spx_option_chain()
    item = get_spxw_chain_item(chain)
    if not item:
        raise HTTPException(status_code=503, detail="SPXW option chain unavailable")
    return {
        "root": "SPXW",
        "expirations": [
            {"date": x.get("expiration-date"), "dte": x.get("days-to-expiration"),
             "strike_count": len(x.get("strikes", []))}
            for x in item.get("expirations", []) if x.get("expiration-date")
        ],
        "source": "tastytrade",
        "quotes_available": False,
        "order_execution_enabled": False,
    }

@router.get("/chain")
def workbench_chain(
    expiration: str = Query(..., pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    user=Depends(require_owner),
):
    if not config.BXK_AUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Authenticated workbench required")
    if not (config.TASTYTRADE_CLIENT_SECRET and config.TASTYTRADE_REFRESH_TOKEN):
        raise HTTPException(status_code=503, detail="Tastytrade market-data connection not configured")
    chain = tastytrade_api.get_spx_option_chain()
    item = get_spxw_chain_item(chain)
    if not item:
        raise HTTPException(status_code=503, detail="SPXW option chain unavailable")
    match = next((x for x in item.get("expirations", [])
                  if x.get("expiration-date") == expiration), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Requested SPXW expiration not listed")
    # Return contract identifiers, never account information or execution credentials.
    return {
        "root": "SPXW",
        "expiration": expiration,
        "strikes": [
            {"strike": x.get("strike-price"),
             "put_symbol": x.get("put-streamer-symbol"),
             "call_symbol": x.get("call-streamer-symbol")}
            for x in match.get("strikes", [])[:1500]
        ],
        "quotes_available": False,
        "source": "tastytrade",
    }

@router.get("/quotes")
def workbench_quotes(
    expiration: str = Query(..., pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    min_strike: float = Query(..., gt=0),
    max_strike: float = Query(..., gt=0),
    user=Depends(require_owner),
):
    """Return only quote fields for listed SPXW contracts in a bounded strike range."""
    if not config.BXK_AUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Authenticated workbench required")
    if not (config.TASTYTRADE_CLIENT_SECRET and config.TASTYTRADE_REFRESH_TOKEN):
        raise HTTPException(status_code=503, detail="Tastytrade market data not configured")
    if max_strike <= min_strike or max_strike - min_strike > 500:
        raise HTTPException(status_code=400, detail="Strike range must be positive and at most 500 points")
    chain = tastytrade_api.get_spx_option_chain()
    item = get_spxw_chain_item(chain)
    if not item:
        raise HTTPException(status_code=503, detail="SPXW option chain unavailable")
    selected = next((x for x in item.get("expirations", [])
                     if x.get("expiration-date") == expiration), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Expiration not listed")
    contracts = []
    for row in selected.get("strikes", []):
        try:
            strike = float(row.get("strike-price"))
        except (TypeError, ValueError):
            continue
        if min_strike <= strike <= max_strike:
            for option_type, field in (("put", "put-streamer-symbol"), ("call", "call-streamer-symbol")):
                symbol = row.get(field)
                if symbol:
                    contracts.append((str(symbol), option_type, strike))
    if len(contracts) > 160:
        raise HTTPException(status_code=400, detail="Narrow strike range to 80 or fewer strikes")
    symbols = [c[0] for c in contracts]
    raw = tastytrade_api.get_option_quotes(symbols)
    lookup = {str(q.get("symbol") or q.get("instrument-symbol") or ""): q for q in raw}
    quotes = []
    for symbol, option_type, strike in contracts:
        q = lookup.get(symbol)
        if not q:
            continue
        try:
            bid = float(q.get("bid") or q.get("bid-price"))
            ask = float(q.get("ask") or q.get("ask-price"))
        except (TypeError, ValueError):
            continue
        if not (0 <= bid <= ask):
            continue
        quotes.append({"type": option_type, "strike": strike, "bid": bid,
                       "ask": ask, "symbol": symbol,
                       "timestamp": q.get("timestamp") or q.get("quote-time")})
    return {"root": "SPXW", "expiration": expiration, "source": "tastytrade",
            "quotes": quotes, "requested_contracts": len(contracts),
            "received_quotes": len(quotes), "order_execution_enabled": False}
