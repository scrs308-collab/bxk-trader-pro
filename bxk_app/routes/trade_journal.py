from fastapi import (
    APIRouter,
    Depends,
)

from bxk_app.brokers.tastytrade import (
    broker,
)

from bxk_app.authorization import (
    require_owner_or_auth_disabled,
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
        require_owner_or_auth_disabled
    ),
):
    return get_trade_journal_summary(
        user_context=user_context,
    )


@router.get("/trades")
def trade_journal_trades(
    limit: int = 25,
    user_context: dict = Depends(
        require_owner_or_auth_disabled
    ),
):
    return get_trade_journal_trades(
        user_context=user_context,
        limit=limit,
    )

@router.post("/backfill")
def trade_journal_backfill(
    days: int = 30,
    dry_run: bool = True,
    user_context: dict = Depends(
        require_owner_or_auth_disabled
    ),
):
    return backfill_trade_journal(
        broker_client=broker,
        user_context=user_context,
        days=days,
        dry_run=dry_run,
    )
