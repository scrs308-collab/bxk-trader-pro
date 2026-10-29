"""Owner preview market-data routes; no order operations."""
import os
import math
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from bxk_app.authorization import require_owner
from bxk_app.database import get_db

router = APIRouter(prefix="/api/workbench-preview", tags=["Workbench preview"])

def preview_access(response: Response, user=Depends(require_owner)):
    if os.getenv("BXK_WORKBENCH_PREVIEW_ENABLED", "").strip().lower() != "true":
        raise HTTPException(404, "Not found")
    response.headers["Cache-Control"]="no-store"
    return user

def scoped_broker(session, user):
    from bxk_app.services.broker_connection_service import (
        get_user_tastytrade_connection, resolve_tastytrade_broker,
        import_legacy_owner_connection, BrokerVerificationError,
        BrokerConnectionInvalid, BrokerConnectionRequired,
    )
    from uuid import UUID
    try:
        user_id = UUID(str(user.get("user_id") or ""))
    except (ValueError, TypeError):
        raise HTTPException(409, "A user-specific broker connection is required") from None
    connection = get_user_tastytrade_connection(session, user_id=user_id)
    if connection is None:
        try:
            connection = import_legacy_owner_connection(session, user_context=user)
        except (BrokerVerificationError, BrokerConnectionInvalid):
            session.rollback()
            raise HTTPException(409, "Existing owner connection could not be verified") from None
    if connection is None or not connection.is_verified:
        raise HTTPException(409, "Connect and verify this user's tastytrade account first")
    try:
        return resolve_tastytrade_broker(session, user_context=user)
    except (BrokerConnectionInvalid, BrokerConnectionRequired):
        raise HTTPException(409, "This user's broker connection is unavailable") from None

def listed_expirations(broker):
    # The request uses the resolved user's authenticated transport.
    response = broker._request("GET", "/option-chains/SPX/nested")
    if response is None:
        raise HTTPException(503, "SPXW chain unavailable")
    try:
        items = response.json().get("data", {}).get("items", [])
        item = next((x for x in items if x.get("root-symbol") == "SPXW"), None)
        if item is None:
            raise ValueError("SPXW missing")
        rows = [{"date": x["expiration-date"], "dte": x.get("days-to-expiration")}
                for x in item.get("expirations", []) if x.get("expiration-date")]
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(503, "SPXW chain unavailable") from None
    return {"root": "SPXW", "expirations": rows, "source": "tastytrade",
            "user_scoped": True, "order_submission_available": False}

@router.get("/expirations")
def expirations(user=Depends(preview_access), session: Session=Depends(get_db)):
    return listed_expirations(scoped_broker(session, user))

def spx_reference(broker):
    quote = broker.get_index_quote("SPX")
    if not isinstance(quote, dict) or str(quote.get("symbol") or quote.get("instrument-symbol") or "").lstrip("$").upper() != "SPX":
        raise HTTPException(503, "SPX index quote unavailable")
    stamp = quote.get("updated-at") or quote.get("updatedAt") or quote.get("timestamp")
    try:
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))).total_seconds()
        if not -60 <= age <= 120:
            raise ValueError("Stale quote")
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(503, "Fresh SPX index quote required") from None
    # Closing prices must never be presented as a current SPX reference.
    for field in ("last", "last-price", "mark", "mark-price"):
        try:
            price = float(quote.get(field))
        except (ValueError, TypeError):
            continue
        if math.isfinite(price) and 1000 < price < 100000:
            return {"symbol":"SPX", "price":price, "timestamp":stamp,
                    "price_field":field, "source":"tastytrade", "fresh":True,
                    "user_scoped":True, "order_submission_available":False}
    raise HTTPException(503, "SPX quote has no usable current price")

@router.get("/reference")
def reference(user=Depends(preview_access), session: Session=Depends(get_db)):
    return spx_reference(scoped_broker(session,user))

def quote_snapshot(broker, expiration, min_strike, max_strike):
    try:
        date.fromisoformat(expiration)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid expiration") from None
    if not all(math.isfinite(x) for x in (min_strike, max_strike)) or not 0 < min_strike < max_strike or max_strike-min_strike > 400:
        raise HTTPException(400, "Use a positive strike range of at most 400 points")
    response = broker._request("GET", "/option-chains/SPX/nested")
    try:
        items = response.json().get("data", {}).get("items", []) if response is not None else []
        root = next((x for x in items if x.get("root-symbol") == "SPXW"), {})
        selected = next((x for x in root.get("expirations", []) if x.get("expiration-date") == expiration), None)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(503, "SPXW chain unavailable") from None
    if not root:
        raise HTTPException(503, "SPXW chain unavailable")
    if selected is None:
        raise HTTPException(404, "SPXW expiration not listed")
    contracts = {}
    compact = expiration[2:4]+expiration[5:7]+expiration[8:10]
    for row in selected.get("strikes", []):
        try:
            strike = float(row["strike-price"])
        except (KeyError, ValueError, TypeError):
            continue
        if math.isfinite(strike) and min_strike <= strike <= max_strike:
            for kind, letter in (("put", "P"), ("call", "C")):
                symbol = f"SPXW  {compact}{letter}{round(strike*1000):08d}"
                contracts[symbol] = (kind, strike)
    if len(contracts) > 160:
        raise HTTPException(400, "Narrow range to 80 or fewer strikes")
    symbols = list(contracts)
    raw = []
    for start in range(0, len(symbols), 80):
        raw.extend(broker.get_option_quotes(symbols[start:start+80]))
    now = datetime.now(timezone.utc)
    quotes = []
    for row in raw:
        symbol = row.get("symbol") or row.get("instrument-symbol")
        if symbol not in contracts:
            continue
        try:
            bid = float(row.get("bid") if row.get("bid") is not None else row.get("bid-price"))
            ask = float(row.get("ask") if row.get("ask") is not None else row.get("ask-price"))
        except (ValueError, TypeError):
            continue
        if not (math.isfinite(bid) and math.isfinite(ask) and 0 <= bid <= ask):
            continue
        stamp = row.get("updated-at") or row.get("updatedAt") or row.get("timestamp")
        fresh = False
        try:
            age = (now-datetime.fromisoformat(str(stamp).replace("Z","+00:00"))).total_seconds()
            fresh = -60 <= age <= 120
        except (ValueError, TypeError, OverflowError):
            pass
        kind, strike = contracts[symbol]
        quotes.append({"symbol":symbol, "type":kind, "strike":strike, "bid":bid, "ask":ask,
                       "timestamp":stamp if isinstance(stamp,str) else None, "fresh":fresh})
    return {"root":"SPXW", "expiration":expiration, "source":"tastytrade", "user_scoped":True,
            "quotes":quotes, "requested_contracts":len(contracts), "received_quotes":len(quotes),
            "checked_at":now.isoformat(), "order_submission_available":False}

@router.get("/quotes")
def quotes(
    expiration: str=Query(..., pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    min_strike: float=Query(..., gt=0), max_strike: float=Query(..., gt=0),
    user=Depends(preview_access), session: Session=Depends(get_db),
):
    return quote_snapshot(scoped_broker(session,user), expiration,min_strike,max_strike)

@router.get("/condors")
def condors(
    expiration: str=Query(..., pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    min_strike: float=Query(..., gt=0), max_strike: float=Query(..., gt=0),
    spot: float=Query(..., gt=0), expected_move: float=Query(..., gt=0),
    width: float=Query(10, gt=0, le=100), minimum_pop: float=Query(70, ge=1, le=99),
    user=Depends(preview_access), session: Session=Depends(get_db),
):
    from bxk_app.services.workbench_analysis import analyze_condors
    snapshot=quote_snapshot(scoped_broker(session,user),expiration,min_strike,max_strike)
    try:
        result=analyze_condors(snapshot,spot,expected_move,width,minimum_pop)
    except ValueError:
        raise HTTPException(400,"Invalid analysis inputs") from None
    return dict(result,expiration=expiration,user_scoped=True,checked_at=snapshot["checked_at"])


from pydantic import BaseModel, Field, ConfigDict

class PositionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expiration: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    min_strike: float = Field(gt=0)
    max_strike: float = Field(gt=0)
    spot: float = Field(gt=0)
    expected_move: float = Field(gt=0)
    width: float = Field(gt=0,le=100)
    minimum_pop: float = Field(ge=1,le=99)
    put_short: float = Field(gt=0)
    put_long: float = Field(gt=0)
    call_short: float = Field(gt=0)
    call_long: float = Field(gt=0)
    credit_points: float = Field(gt=0)

def reviewed_position(result, payload):
    keys=("put_short","put_long","call_short","call_long")
    selected=next((c for c in result["condors"]
                   if all(c[k]==getattr(payload,k) for k in keys)),None)
    if selected is None:
        raise HTTPException(409,"Position no longer matches fresh analysis; reload results")
    if abs(selected["credit_points"]-payload.credit_points)>0.10+1e-9:
        raise HTTPException(409,"Premium changed; reload and select again")
    return {"position":selected,"expiration":payload.expiration,"contracts":1,
            "quote_checked_at":result["checked_at"],"user_scoped":True,
            "buying_power_verified":False,"broker_dry_run_available":False,
            "review_lock_issued":False,"order_submission_available":False,
            "message":"Fresh snapshot verified. Broker risk and buying power review still required."}

def refresh_selected_position(broker, payload):
    """Reprice these exact legs, independently of the top-ten discovery ranking."""
    from bxk_app.services.workbench_analysis import analyze_condors
    snapshot = quote_snapshot(broker, payload.expiration, payload.min_strike, payload.max_strike)
    selected_legs = {("put", payload.put_short), ("put", payload.put_long),
                     ("call", payload.call_short), ("call", payload.call_long)}
    selected_snapshot = dict(snapshot, quotes=[q for q in snapshot.get("quotes", [])
        if (q.get("type"), q.get("strike")) in selected_legs])
    try:
        result = analyze_condors(selected_snapshot, payload.spot, payload.expected_move,
                                 payload.width, payload.minimum_pop)
    except ValueError:
        raise HTTPException(400, "Invalid analysis inputs") from None
    result["checked_at"] = snapshot["checked_at"]
    keys = ("put_short", "put_long", "call_short", "call_long")
    selected = next((c for c in result["condors"]
                     if all(c[k] == getattr(payload, k) for k in keys)), None)
    if selected is None:
        raise HTTPException(409, "Selected legs no longer meet the fresh quote, wing-width, OTM or minimum POP requirements. Reload analysis and select another position.")
    # This is analysis/dry-run only: price the refreshed snapshot, never the old row.
    refreshed_payload = payload.model_copy(update={"credit_points": selected["credit_points"]})
    review = reviewed_position(result, refreshed_payload)
    review["previous_credit_points"] = payload.credit_points
    review["credit_change_dollars"] = round((selected["credit_points"] - payload.credit_points) * 100, 2)
    return review, refreshed_payload

@router.post("/position-review")
def position_review(payload:PositionReviewRequest,user=Depends(preview_access),session:Session=Depends(get_db)):
    review, _ = refresh_selected_position(scoped_broker(session, user), payload)
    return review

@router.post("/dry-run")
def preview_dry_run(payload:PositionReviewRequest,user=Depends(preview_access),session:Session=Depends(get_db)):
    from bxk_app.services.workbench_dry_run import run_dry_run
    broker = scoped_broker(session, user)
    review, refreshed_payload = refresh_selected_position(broker, payload)
    result = run_dry_run(review, refreshed_payload, broker, session, user)
    return dict(result, position=review["position"],
                previous_credit_points=review["previous_credit_points"],
                credit_change_dollars=review["credit_change_dollars"],
                quote_checked_at=review["quote_checked_at"])
