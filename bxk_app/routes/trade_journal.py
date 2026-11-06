from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    require_owner_or_beta,
)
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    resolve_broker,
)

from bxk_app.services.trade_journal_backfill_service import (
    backfill_trade_journal,
)

from bxk_app.services.trade_journal_service import (
    get_trade_journal_summary,
    get_trade_journal_trades,
)


router = APIRouter(
    prefix="/api/trade-journal",
    tags=["trade-journal"],
)


@router.get("/summary")
def trade_journal_summary(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
):
    return get_trade_journal_summary(
        user_context=user_context,
    )


@router.get("/trades")
def trade_journal_trades(
    limit: int = 25,
    include_open: bool = False,
    user_context: dict = Depends(
        require_owner_or_beta
    ),
):
    return get_trade_journal_trades(
        user_context=user_context,
        limit=limit,
        include_open=include_open,
    )

@router.post("/backfill")
def trade_journal_backfill(
    days: int = 30,
    dry_run: bool = True,
    user_context: dict = Depends(
        require_owner_or_beta
    ),
    session: Session = Depends(
        get_db
    ),
):
    role_value = user_context.get(
        "role"
    )

    if hasattr(
        role_value,
        "value",
    ):
        role_value = role_value.value

    role = str(
        role_value or ""
    ).strip().upper()

    if role not in {
        "OWNER",
        "BETA",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Trade-journal backfill requires "
                "OWNER or BETA permission."
            ),
        )

    try:
        broker_client = (
            resolve_broker(
                session,
                user_context=user_context,
            )
        )

    except BrokerConnectionRequired as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except BrokerConnectionInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return backfill_trade_journal(
        broker_client=broker_client,
        user_context=user_context,
        days=days,
        dry_run=dry_run,
    )


@router.get("/broker-history")
def broker_trade_history(
    days: int = 30,
    user_context: dict = Depends(require_owner_or_beta),
    session: Session = Depends(get_db),
):
    """Read-only filled broker orders across supported instruments.

    These are execution records, not reconciled round-trip P/L.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from bxk_app.services.trade_journal_service import _order_fill_timestamp

    days = max(1, min(int(days), 90))
    today = datetime.now(ZoneInfo("America/New_York")).date()
    try:
        broker = resolve_broker(session, user_context=user_context)
    except BrokerConnectionRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BrokerConnectionInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not hasattr(broker, "get_orders"):
        raise HTTPException(status_code=422, detail="Broker order history unavailable.")
    account = broker.get_first_account_number()
    if not account:
        raise HTTPException(status_code=409, detail="Broker account unavailable.")
    orders = broker.get_orders(
        account_number=account,
        start_date=(today - timedelta(days=days)).isoformat(),
        end_date=today.isoformat(),
        statuses=["Filled"],
    )
    if getattr(broker, "last_error", None):
        raise HTTPException(status_code=502, detail="Broker history request failed.")
    results = []
    seen = set()
    for order in orders or []:
        if not isinstance(order, dict):
            continue
        order_id = str(order.get("id") or "").strip()
        if not order_id or order_id in seen:
            continue
        seen.add(order_id)
        legs = order.get("legs") or []
        timestamp = _order_fill_timestamp(order)
        results.append({
            "id": order_id,
            "filled_at": timestamp.isoformat() if timestamp else None,
            "status": order.get("status"),
            "price": order.get("average-fill-price") or order.get("price"),
            "price_effect": order.get("price-effect"),
            "legs": [
                {
                    "symbol": leg.get("symbol"),
                    "action": leg.get("action"),
                    "quantity": leg.get("quantity"),
                }
                for leg in legs if isinstance(leg, dict)
            ],
        })
    return {"available": True, "count": len(results), "orders": results}
