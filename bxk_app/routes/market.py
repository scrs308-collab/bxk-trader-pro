from datetime import datetime

from fastapi import APIRouter

from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.scoring import run_trade_quality


router = APIRouter(
    prefix="/api",
    tags=["Market"],
)


def safe_market_value(
    market,
    field_name,
    default=None,
):
    """
    Safely read a value from either an object or dictionary.
    """

    if isinstance(market, dict):
        return market.get(
            field_name,
            default,
        )

    return getattr(
        market,
        field_name,
        default,
    )


@router.get("/refresh-market")
def refresh_market():
    market_engine.refresh()

    return {
        "status": "market refresh complete",
        "market_engine": market_engine.get_status(),
        "market_snapshot": market_data.get_snapshot(),
    }


@router.get("/market-brief")
def market_brief():
    market = run_trade_quality()

    market_regime = safe_market_value(
        market,
        "market_regime",
        "WAIT",
    )

    trend = safe_market_value(
        market,
        "trend",
        "UNKNOWN",
    )

    vix_state = safe_market_value(
        market,
        "vix_state",
        "UNKNOWN",
    )

    expected_move_state = safe_market_value(
        market,
        "expected_move_state",
        "UNKNOWN",
    )

    iv_rank_state = safe_market_value(
        market,
        "iv_rank_state",
        "UNKNOWN",
    )

    if market_regime == "TRADE":
        summary = (
            f"Market conditions support trading. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            f"Current conditions favor premium-selling strategies."
        )
    else:
        summary = (
            f"Market conditions are not ideal. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            f"Waiting is favored until conditions improve."
        )

    return {
        "title": "Market Narrative",
        "summary": summary,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
    }


@router.get("/live-market")
def live_market():
    return market_engine.update()


@router.get("/debug/market")
def debug_market():
    return {
        "status": "OK",
        "spx": market_data.spx,
        "vix": market_data.vix,
        "vix1d": market_data.vix1d,
        "expected_move": market_data.expected_move,
        "snapshot": market_data.get_snapshot(),
    }