from datetime import datetime

from fastapi import APIRouter

from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine


router = APIRouter(
    prefix="/api",
    tags=["Debug"],
)


@router.get("/debug")
def debug():
    return {
        "app": "BXK Trader Pro",
        "version": "6.1",
        "status": "debug route active",
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
    }