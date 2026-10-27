"""Owner preview market-data routes; no order operations."""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from bxk_app.authorization import require_owner
from bxk_app.database import get_db

router = APIRouter(prefix="/api/workbench-preview", tags=["Workbench preview"])

def preview_access(user=Depends(require_owner)):
    if os.getenv("BXK_WORKBENCH_PREVIEW_ENABLED", "").strip().lower() != "true":
        raise HTTPException(404, "Not found")
    return user

def scoped_broker(session, user):
    from bxk_app.services.broker_connection_service import (
        get_user_tastytrade_connection, resolve_tastytrade_broker,
        BrokerConnectionInvalid, BrokerConnectionRequired,
    )
    from uuid import UUID
    try:
        user_id = UUID(str(user.get("user_id") or ""))
    except (ValueError, TypeError):
        raise HTTPException(409, "A user-specific broker connection is required") from None
    connection = get_user_tastytrade_connection(session, user_id=user_id)
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
