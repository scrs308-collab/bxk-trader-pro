from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    get_authenticated_user,
)
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    resolve_tastytrade_broker,
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
        get_authenticated_user
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
        get_authenticated_user
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
        get_authenticated_user
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
            resolve_tastytrade_broker(
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
