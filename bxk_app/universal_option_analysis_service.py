from __future__ import annotations

from bxk_app.universal_underlying_service import (
    discover_underlying,
)
from bxk_app.option_chain_service import (
    calculate_atm_straddle_expected_move,
)
from bxk_app.underlying_condor_scanner import (
    build_and_price_underlying_condor,
)
from bxk_app.underlying_stability import (
    calculate_underlying_stability_metrics,
)
from bxk_app.condor_stability_score import (
    calculate_condor_stability_score,
)
from bxk_app.range_expansion_pressure import (
    calculate_range_expansion_pressure,
)
from bxk_app.market_session import (
    get_market_session_phase,
)
from bxk_app.underlying_decision import (
    evaluate_underlying_condor_decision,
)


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number <= 0:
        return None

    return number


def analyze_underlying(
    symbol: str,
    *,
    days_to_expiration=None,
    wing_width=None,
):
    """
    Universal option-underlying analysis.

    Pipeline:
      discovery
      -> exact DTE validation
      -> option-chain expected move
      -> condor construction
      -> live pricing

    SAFETY:
    This service is observation-only and cannot authorize
    or submit an order.
    """

    discovery = discover_underlying(
        symbol
    )

    requested_dte = _safe_int(
        days_to_expiration
    )

    requested_width = (
        _safe_positive_float(
            wing_width
        )
    )

    available_dtes = sorted(
        {
            item.get("dte")
            for item in discovery.get(
                "expirations",
                [],
            )
            if item.get("dte")
            is not None
        }
    )

    result = {
        "symbol": discovery.get(
            "symbol"
        ),
        "price": discovery.get(
            "price"
        ),

        "instrument_family": (
            discovery.get(
                "instrument_family"
            )
        ),
        "delivery_style": (
            discovery.get(
                "delivery_style"
            )
        ),
        "verified_profile": (
            discovery.get(
                "verified_profile",
                False,
            )
        ),
        "exercise_style": (
            discovery.get(
                "exercise_style"
            )
        ),
        "early_assignment_risk": (
            discovery.get(
                "early_assignment_risk"
            )
        ),

        "requested_dte":
            requested_dte,

        "requested_wing_width":
            requested_width,

        "available_dtes":
            available_dtes,

        "expected_move_available":
            False,
        "expected_move": None,
        "expected_move_pct": None,
        "expected_move_detail": None,

        "candidate_available":
            False,
        "candidate_pricing_ready":
            False,
        "candidate_preview": None,
        "candidate_result": None,

        "stability_available": False,
        "stability_signal_ready": False,
        "stability_metrics": None,
        "range_expansion_pressure": None,
        "stability_score": None,
        "stability_score_detail": None,

        "decision": None,
        "strategy_status": None,
        "market_permission": None,
        "final_decision": "NO TRADE",
        "decision_reason_code": None,

        "analysis_ready": False,

        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,

        "reason_code":
            discovery.get(
                "reason_code"
            ),
    }

    # -------------------------------------------------
    # DISCOVERY
    # -------------------------------------------------

    if (
        discovery.get(
            "analysis_enabled"
        )
        is not True
    ):
        return result

    # -------------------------------------------------
    # EXACT EXPIRATION
    #
    # Never substitute a nearby DTE.
    # -------------------------------------------------

    if requested_dte is None:
        result["reason_code"] = (
            "DTE_REQUIRED"
        )
        return result

    if (
        requested_dte
        not in available_dtes
    ):
        result["reason_code"] = (
            "DTE_UNAVAILABLE"
        )
        return result

    # -------------------------------------------------
    # EXPECTED MOVE
    # -------------------------------------------------

    try:
        expected = (
            calculate_atm_straddle_expected_move(
                discovery["symbol"],
                discovery["price"],
                days_to_expiration=(
                    requested_dte
                ),
            )
        )
    except Exception:
        result["reason_code"] = (
            "EXPECTED_MOVE_ERROR"
        )
        return result

    result[
        "expected_move_detail"
    ] = expected

    result[
        "expected_move_available"
    ] = (
        expected.get("available")
        is True
    )

    result["expected_move"] = (
        expected.get(
            "expected_move"
        )
    )

    result["expected_move_pct"] = (
        expected.get(
            "expected_move_pct"
        )
    )

    if (
        result[
            "expected_move_available"
        ]
        is not True
    ):
        result["reason_code"] = (
            expected.get(
                "reason_code",
                "EXPECTED_MOVE_UNAVAILABLE",
            )
        )
        return result

    # -------------------------------------------------
    # UNIVERSAL STABILITY
    # -------------------------------------------------

    try:
        session = (
            get_market_session_phase()
        )
    except Exception:
        session = {
            "session_phase": None,
            "minutes_since_open": None,
            "market_status": "UNKNOWN",
        }

    market_status = str(
        session.get(
            "market_status",
            "LIVE",
        )
        or "LIVE"
    ).upper()

    stability = (
        calculate_underlying_stability_metrics(
            symbol=discovery["symbol"],
            underlying_price=(
                discovery.get("price")
            ),
            expected_move=(
                expected.get(
                    "expected_move"
                )
            ),
            session_open=(
                discovery.get(
                    "session_open"
                )
            ),
            day_high=(
                discovery.get(
                    "day_high"
                )
            ),
            day_low=(
                discovery.get(
                    "day_low"
                )
            ),
            prev_close=(
                discovery.get(
                    "prev_close"
                )
            ),
            expected_move_source=(
                expected.get(
                    "source"
                )
            ),
            market_status=market_status,
        )
    )

    result[
        "stability_metrics"
    ] = stability

    result[
        "stability_available"
    ] = (
        stability.get("available")
        is True
    )

    result[
        "stability_signal_ready"
    ] = (
        stability.get(
            "signal_ready"
        )
        is True
    )

    pressure = (
        calculate_range_expansion_pressure(
            signal_ready=(
                stability.get(
                    "signal_ready"
                )
            ),
            session_phase=(
                session.get(
                    "session_phase"
                )
            ),
            minutes_since_open=(
                session.get(
                    "minutes_since_open"
                )
            ),
            directional_consumed_pct=(
                stability.get(
                    "directional_consumed_pct"
                )
            ),
        )
    )

    result[
        "range_expansion_pressure"
    ] = pressure

    stability_score = (
        calculate_condor_stability_score(
            signal_ready=(
                stability.get(
                    "signal_ready"
                )
            ),
            directional_consumed_pct=(
                stability.get(
                    "directional_consumed_pct"
                )
            ),
            current_displacement_pct=(
                stability.get(
                    "current_displacement_pct"
                )
            ),
            range_band_consumed_pct=(
                stability.get(
                    "range_band_consumed_pct"
                )
            ),
            overnight_gap_pct=(
                stability.get(
                    "overnight_gap_pct"
                )
            ),
            pressure_ratio=(
                pressure.get(
                    "pressure_ratio"
                )
                if isinstance(
                    pressure,
                    dict,
                )
                else None
            ),
        )
    )

    result[
        "stability_score_detail"
    ] = stability_score

    result["stability_score"] = (
        stability_score.get(
            "score"
        )
        if isinstance(
            stability_score,
            dict,
        )
        else None
    )

    # -------------------------------------------------
    # CANDIDATE
    # -------------------------------------------------

    candidate_result = (
        build_and_price_underlying_condor(
            discovery["symbol"],
            discovery["price"],
            expected["expected_move"],
            wing_width=requested_width,
            days_to_expiration=(
                requested_dte
            ),
        )
    )

    result[
        "candidate_result"
    ] = candidate_result

    result[
        "candidate_available"
    ] = (
        candidate_result.get(
            "available"
        )
        is True
    )

    result[
        "candidate_pricing_ready"
    ] = (
        candidate_result.get(
            "pricing_ready"
        )
        is True
    )

    result[
        "candidate_preview"
    ] = candidate_result.get(
        "candidate"
    )

    result["reason_code"] = (
        candidate_result.get(
            "reason_code",
            "CANDIDATE_UNAVAILABLE",
        )
    )

    result["analysis_ready"] = (
        result[
            "expected_move_available"
        ]
        and result[
            "candidate_available"
        ]
        and result[
            "candidate_pricing_ready"
        ]
    )

    decision = (
        evaluate_underlying_condor_decision(
            symbol=discovery["symbol"],
            stability_score_detail=(
                stability_score
            ),
            candidate_result=(
                candidate_result
            ),
            verified_profile=(
                discovery.get(
                    "verified_profile",
                    False,
                )
            ),
        )
    )

    result["decision"] = decision

    result["strategy_status"] = (
        decision.get(
            "strategy_status"
        )
    )

    result["market_permission"] = (
        decision.get(
            "market_permission"
        )
    )

    result["final_decision"] = (
        decision.get(
            "final_decision"
        )
    )

    result["decision_reason_code"] = (
        decision.get(
            "reason_code"
        )
    )

    # Explicit safety boundary.
    result["signal_ready"] = False
    result["execution_enabled"] = False
    result["observation_only"] = True

    return result
