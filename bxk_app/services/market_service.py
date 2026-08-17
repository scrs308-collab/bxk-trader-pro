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


def get_recent_condor_risk_summaries(
    limit=10,
):
    """
    Return recent completed Condor Stability daily summaries.

    Today's file is always excluded because it may represent
    an incomplete trading session.

    Observation-only. This data does not influence trading
    decisions or order execution.
    """

    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = 10

    requested_limit = max(
        1,
        min(30, requested_limit),
    )

    today = date.today().isoformat()

    if not DEFAULT_LOG_DIR.exists():
        return {
            "status": "NO_DATA",
            "count": 0,
            "limit": requested_limit,
            "summaries": [],
        }

    paths = sorted(
        DEFAULT_LOG_DIR.glob("*.csv"),
        reverse=True,
    )

    summaries = []

    for path in paths:
        # Never treat today's partial file as completed history.
        if path.stem == today:
            continue

        summary = summarize_condor_risk_day(
            path
        )

        if summary.get("available") is not True:
            continue

        summaries.append(summary)

        if len(summaries) >= requested_limit:
            break

    return {
        "status": (
            "AVAILABLE"
            if summaries
            else "NO_DATA"
        ),
        "count": len(summaries),
        "limit": requested_limit,
        "summaries": summaries,
    }
