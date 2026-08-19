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
from bxk_app.underlyings import get_underlying_config
from bxk_app.option_chain_service import (
    calculate_atm_straddle_expected_move,
)
from bxk_app.qqq_stability import (
    calculate_qqq_stability_metrics,
)
from bxk_app.market_session import (
    get_market_session_phase,
)
from bxk_app.range_expansion_pressure import (
    calculate_range_expansion_pressure,
)
from bxk_app.condor_stability_score import (
    calculate_condor_stability_score,
)
from bxk_app.underlying_condor_scanner import (
    build_and_price_underlying_condor,
)
from bxk_app.qqq_decision import (
    evaluate_qqq_condor_decision,
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


def _quote_price(quote):
    if not isinstance(quote, dict):
        return 0.0

    for key in (
        "last",
        "last_price",
        "last-price",
        "mark",
        "mid",
    ):
        value = quote.get(key)

        if value is None:
            continue

        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue

    return 0.0


def _quote_number(
    quote,
    *keys,
):
    if not isinstance(quote, dict):
        return None

    for key in keys:
        value = quote.get(key)

        if value is None:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return None


def get_live_market(underlying: str = "SPX"):
    config = get_underlying_config(underlying)

    # Continue using the existing market engine so SPX behavior remains
    # unchanged and the normal SPX/VIX/VIX1D/QQQ refresh still occurs.
    payload = dict(market_engine.update())

    if config.symbol == "SPX":
        payload["underlying"] = "SPX"
        payload["price"] = round(
            float(payload.get("spx") or 0.0),
            2,
        )
        payload["execution_enabled"] = True

        return payload

    # QQQ remains observation-only.
    #
    # It now receives its own option-chain expected move rather
    # than inheriting SPX/VIX data. Trade construction remains
    # disabled until QQQ stability and scanner logic are ready.
    qqq_quote = payload.get("qqq") or market_data.qqq or {}
    qqq_price = _quote_price(qqq_quote)

    try:
        expected_move_result = (
            calculate_atm_straddle_expected_move(
                "QQQ",
                qqq_price,
                days_to_expiration=0,
            )
        )
    except Exception:
        # Fail closed. Market-data enrichment must never make
        # the live-market endpoint unsafe or imply trade readiness.
        expected_move_result = {
            "available": False,
            "signal_ready": False,
            "expected_move": None,
            "expected_move_pct": None,
            "atm_strike": None,
            "call_mid": None,
            "put_mid": None,
            "expiration": None,
            "dte": 0,
            "source": "OPTION_CHAIN_ATM_STRADDLE",
            "reason_code": "QQQ_EXPECTED_MOVE_ERROR",
        }

    expected_move_available = bool(
        expected_move_result.get("available")
    )

    session = get_market_session_phase()

    qqq_stability = (
        calculate_qqq_stability_metrics(
            qqq_price=qqq_price,
            expected_move=(
                expected_move_result.get(
                    "expected_move"
                )
            ),
            session_open=_quote_number(
                qqq_quote,
                "open",
                "open-price",
            ),
            day_high=_quote_number(
                qqq_quote,
                "day-high-price",
                "high",
            ),
            day_low=_quote_number(
                qqq_quote,
                "day-low-price",
                "low",
            ),
            prev_close=_quote_number(
                qqq_quote,
                "prev-close",
                "prev-close-price",
            ),
            expected_move_source=(
                expected_move_result.get(
                    "source"
                )
            ),
            market_status=payload.get(
                "market_status"
            ),
        )
    )

    expansion_pressure = (
        calculate_range_expansion_pressure(
            directional_consumed_pct=(
                qqq_stability.get(
                    "directional_consumed_pct"
                )
            ),
            minutes_since_open=(
                session.get(
                    "minutes_since_open"
                )
            ),
            session_phase=(
                session.get(
                    "session_phase"
                )
            ),
            signal_ready=(
                qqq_stability.get(
                    "signal_ready",
                    False,
                )
            ),
        )
    )

    qqq_stability[
        "session_phase"
    ] = session.get(
        "session_phase"
    )

    qqq_stability[
        "minutes_since_open"
    ] = session.get(
        "minutes_since_open"
    )

    qqq_stability[
        "range_expansion_pressure"
    ] = expansion_pressure

    stability_score = (
        calculate_condor_stability_score(
            signal_ready=(
                qqq_stability.get(
                    "signal_ready",
                    False,
                )
            ),
            directional_consumed_pct=(
                qqq_stability.get(
                    "directional_consumed_pct"
                )
            ),
            current_displacement_pct=(
                qqq_stability.get(
                    "current_displacement_pct"
                )
            ),
            range_band_consumed_pct=(
                qqq_stability.get(
                    "range_band_consumed_pct"
                )
            ),
            overnight_gap_pct=(
                qqq_stability.get(
                    "overnight_gap_pct"
                )
            ),
            pressure_ratio=(
                expansion_pressure.get(
                    "pressure_ratio"
                )
            ),
        )
    )

    qqq_stability[
        "stability_score"
    ] = stability_score

    # Build and price a QQQ candidate for observation only.
    #
    # SAFETY:
    # This does not make QQQ signal-ready and cannot enable
    # order execution.
    if expected_move_available:
        try:
            candidate_result = (
                build_and_price_underlying_condor(
                    "QQQ",
                    qqq_price,
                    expected_move_result.get(
                        "expected_move"
                    ),
                    wing_width=(
                        config.default_wing_width
                    ),
                    days_to_expiration=0,
                )
            )
        except Exception:
            candidate_result = {
                "available": False,
                "pricing_ready": False,
                "signal_ready": False,
                "execution_enabled": False,
                "observation_only": True,
                "underlying": "QQQ",
                "dte": 0,
                "candidate": None,
                "reason_code": (
                    "CONDOR_PREVIEW_ERROR"
                ),
            }
    else:
        candidate_result = {
            "available": False,
            "pricing_ready": False,
            "signal_ready": False,
            "execution_enabled": False,
            "observation_only": True,
            "underlying": "QQQ",
            "dte": 0,
            "candidate": None,
            "reason_code": (
                "EXPECTED_MOVE_UNAVAILABLE"
            ),
        }

    qqq_decision = (
        evaluate_qqq_condor_decision(
            stability_score_detail=(
                stability_score
            ),
            candidate_result=(
                candidate_result
            ),
        )
    )

    if not expected_move_available:
        reason_code = (
            expected_move_result.get(
                "reason_code"
            )
            or "QQQ_EXPECTED_MOVE_UNAVAILABLE"
        )

    elif (
        qqq_stability.get(
            "signal_ready"
        )
        is not True
    ):
        reason_code = (
            qqq_stability.get(
                "reason_code"
            )
            or "QQQ_STABILITY_NOT_READY"
        )

    elif (
        expansion_pressure.get(
            "available"
        )
        is not True
    ):
        pressure_reason = str(
            expansion_pressure.get(
                "reason_code"
            )
            or "PRESSURE_UNAVAILABLE"
        )

        reason_code = (
            f"QQQ_{pressure_reason}"
        )

    elif (
        stability_score.get(
            "available"
        )
        is True
    ):
        reason_code = (
            "QQQ_STABILITY_OBSERVING_EXECUTION_BLOCKED"
        )

    else:
        reason_code = (
            "QQQ_STABILITY_SCORE_UNAVAILABLE"
        )

    positions = payload.get("positions") or []

    underlying_positions = [
        position
        for position in positions
        if str(
            position.get("underlying") or ""
        ).strip().upper() == "QQQ"
    ]

    return {
        "underlying": "QQQ",
        "symbol": "QQQ",
        "price": qqq_price,
        "market_status": payload.get("market_status"),
        "server_time": payload.get("server_time"),
        "quote": qqq_quote,
        "account": payload.get("account"),

        # Account-wide positions remain available for compatibility.
        "positions": positions,

        # Symbol-scoped positions are what the future QQQ UI should use.
        "underlying_positions": underlying_positions,

        "instrument_type": config.instrument_type,
        "settlement": config.settlement,
        "exercise_style": config.exercise_style,
        "early_assignment_risk": (
            config.early_assignment_risk
        ),
        "volatility_reference": (
            config.volatility_reference
        ),
        "expected_move_method": (
            config.expected_move_method
        ),

        "expected_move_available": (
            expected_move_available
        ),
        "expected_move": (
            expected_move_result.get(
                "expected_move"
            )
        ),
        "expected_move_pct": (
            expected_move_result.get(
                "expected_move_pct"
            )
        ),
        "expected_move_source": (
            expected_move_result.get(
                "source"
            )
        ),
        "expected_move_reason_code": (
            expected_move_result.get(
                "reason_code"
            )
        ),
        "atm_strike": (
            expected_move_result.get(
                "atm_strike"
            )
        ),
        "atm_call_mid": (
            expected_move_result.get(
                "call_mid"
            )
        ),
        "atm_put_mid": (
            expected_move_result.get(
                "put_mid"
            )
        ),
        "expiration": (
            expected_move_result.get(
                "expiration"
            )
        ),
        "dte": expected_move_result.get(
            "dte"
        ),

        "session_phase": session.get(
            "session_phase"
        ),
        "minutes_since_open": session.get(
            "minutes_since_open"
        ),

        "stability_signal_ready": (
            qqq_stability.get(
                "signal_ready",
                False,
            )
        ),

        "condor_stability": qqq_stability,

        "range_expansion_pressure": (
            expansion_pressure
        ),

        "stability_score": (
            stability_score.get(
                "score"
            )
        ),

        "stability_score_detail": (
            stability_score
        ),

        "candidate_preview_available": (
            candidate_result.get(
                "available",
                False,
            )
        ),

        "candidate_pricing_ready": (
            candidate_result.get(
                "pricing_ready",
                False,
            )
        ),

        "candidate_preview": (
            candidate_result.get(
                "candidate"
            )
        ),

        "candidate_reason_code": (
            candidate_result.get(
                "reason_code"
            )
        ),

        "candidate_observation_only": (
            candidate_result.get(
                "observation_only",
                True,
            )
        ),

        # Deliberately separate candidate construction from
        # trading authorization.
        "candidate_execution_enabled": False,

        "qqq_decision": qqq_decision,

        "strategy_status": (
            qqq_decision.get(
                "strategy_status"
            )
        ),

        "market_permission": (
            qqq_decision.get(
                "market_permission"
            )
        ),

        "permission_label": (
            qqq_decision.get(
                "permission_label"
            )
        ),

        "final_decision": (
            qqq_decision.get(
                "final_decision"
            )
        ),

        "decision_reason_code": (
            qqq_decision.get(
                "reason_code"
            )
        ),

        "trade_quality_required": (
            qqq_decision.get(
                "trade_quality_required"
            )
        ),

        # Overall QQQ trading remains deliberately blocked.
        "trade_setup": None,
        "signal_ready": False,
        "execution_enabled": False,
        "reason_code": reason_code,
    }


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
