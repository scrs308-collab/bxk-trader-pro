from fastapi import APIRouter, Query

from bxk_app.services.order_builder import (
    build_order,
)
from bxk_app.routes.scanner import (
    get_best_trade,
)

router = APIRouter(
    prefix="/api",
    tags=["Orders"],
)


@router.get("/order-preview")
def order_preview(
    strategy: str = Query("auto"),
    dte: int = Query(1),
    wing_width: int = Query(25),
    contracts: int = Query(1),
):
    """
    Build a broker-independent
    preview order from the current
    best trade.
    """

    result = get_best_trade(
        strategy=strategy,
        dte=dte,
        wing_width=wing_width,
        contracts=contracts,
    )

    trade = result.get(
        "best_trade"
    )

    if not trade:
        return {
            "status": "NO_TRADE",
            "message":
                "No approved trade available.",
        }

    order = build_order(
        trade,
        quantity=contracts,
    )

    return {
        "status": "READY",
        "trade": trade,
        "order": order,
    }