from datetime import date, datetime

from bxk_app.condor_daily_summary import (
    summarize_condor_risk_day,
)
from bxk_app.market_data import market_data
from bxk_app.services.condor_stability_logger import (
    DEFAULT_LOG_DIR,
)
from bxk_app.market_engine import market_engine
from bxk_app.scoring import run_trade_quality


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

def refresh_market_data():
    market_engine.update()

    return {
        "status": "market refresh complete",
        "market_snapshot": market_data.get_snapshot(),
    }


def get_market_brief():
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
            "Market conditions support trading. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            "Current conditions favor premium-selling strategies."
        )
    else:
        summary = (
            "Market conditions are not ideal. "
            f"Trend is {trend}, "
            f"VIX is {vix_state}, "
            f"expected move is {expected_move_state}, "
            f"and IV rank is {iv_rank_state}. "
            "Waiting is favored until conditions improve."
        )

    return {
        "title": "Market Narrative",
        "summary": summary,
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
    }


def get_live_market():
    return market_engine.update()


def get_debug_market():
    return {
        "status": "OK",
        "spx": market_data.spx,
        "vix": market_data.vix,
        "vix1d": market_data.vix1d,
        "expected_move": market_data.expected_move,
        "snapshot": market_data.get_snapshot(),
    }

def get_today_condor_risk_summary():
    """
    Return today's Condor Stability diagnostic summary.

    During regular market hours this may represent a partial
    trading day. After the session closes it becomes the
    completed daily summary.

    This endpoint is observational only and does not influence
    recommendation or order execution.
    """

    trading_date = date.today().isoformat()

    path = (
        DEFAULT_LOG_DIR /
        f"{trading_date}.csv"
    )

    result = summarize_condor_risk_day(path)

    return {
        "trading_date": trading_date,
        "partial_session":
            market_data.market_status() == "LIVE",
        "market_status":
            market_data.market_status(),
        "summary": result,
    }
