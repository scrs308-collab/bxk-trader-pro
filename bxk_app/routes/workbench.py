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
    expiration: str = Query(..., pattern=r"^\\d{4}-\\d{2}-\\d{2}$"),
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
