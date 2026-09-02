"""
Observation-only SPX overnight carry-risk calculator.

The expected-move input is the existing BXK one-trading-day
expected move. It is deliberately NOT described as an
"expected overnight move."

The purpose of V1 is to measure how much short-strike cushion
remains relative to the market's current one-day volatility
expectation and collect evidence for later calibration.
"""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_overnight_carry_risk(
    *,
    spx_close,
    short_put,
    short_call,
    expected_move,
    expected_move_source=None,
    dte=None,
):
    """
    Evaluate whether an open SPX iron condor has enough
    short-strike cushion to justify overnight exposure.

    V1 is observation-only. It cannot execute or close trades.
    """

    spot = _number(spx_close)
    put = _number(short_put)
    call = _number(short_call)
    move = _number(expected_move)

    try:
        clean_dte = (
            int(dte)
            if dte is not None
            else None
        )
    except (TypeError, ValueError):
        clean_dte = None

    source = str(
        expected_move_source
        or "UNKNOWN"
    ).strip().upper()

    if clean_dte is not None and clean_dte <= 0:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "decision": "NOT_APPLICABLE",
            "state": "NONE",
            "reason_code": "NO_OVERNIGHT_EXPIRATION",
        }

    if (
        spot is None
        or put is None
        or call is None
        or move is None
        or spot <= 0
        or put <= 0
        or call <= 0
        or move <= 0
    ):
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "decision": "UNAVAILABLE",
            "state": "UNKNOWN",
            "reason_code":
                "CARRY_RISK_INPUT_UNAVAILABLE",
        }

    put_cushion = round(
        spot - put,
        2,
    )

    call_cushion = round(
        call - spot,
        2,
    )

    if put_cushion <= call_cushion:
        threatened_side = "PUT"
        short_strike = put
        short_cushion = put_cushion
    else:
        threatened_side = "CALL"
        short_strike = call
        short_cushion = call_cushion

    ratio = round(
        short_cushion / move,
        3,
    )

    # These thresholds are intentionally provisional.
    # They create consistent observation buckets while
    # BXK collects enough real overnight outcomes to
    # calibrate them empirically.
    if short_cushion <= 0:
        state = "CRITICAL"
        decision = "DO_NOT_CARRY"
        recommendation = "CLOSE_BEFORE_BELL"
        reason_code = "SHORT_STRIKE_BREACHED"

    elif ratio < 0.50:
        state = "RED"
        decision = "DO_NOT_CARRY"
        recommendation = "CLOSE_BEFORE_BELL"
        reason_code = "CUSHION_LT_HALF_1D_EXPECTED_MOVE"

    elif ratio < 0.75:
        state = "ORANGE"
        decision = "HIGH_RISK"
        recommendation = "REDUCE_OR_CLOSE"
        reason_code = "CUSHION_LT_075_1D_EXPECTED_MOVE"

    elif ratio < 1.00:
        state = "YELLOW"
        decision = "CAUTION"
        recommendation = "REVIEW_BEFORE_CARRY"
        reason_code = "CUSHION_LT_1D_EXPECTED_MOVE"

    else:
        state = "GREEN"
        decision = "CARRY_WITH_MONITORING"
        recommendation = "MONITOR"
        reason_code = "CUSHION_GE_1D_EXPECTED_MOVE"

    return {
        "available": True,
        "observation_only": True,
        "execution_authorized": False,
        "state": state,
        "decision": decision,
        "recommendation": recommendation,
        "reason_code": reason_code,
        "dte": clean_dte,
        "spx_close": round(spot, 2),
        "short_put": round(put, 2),
        "short_call": round(call, 2),
        "put_cushion": put_cushion,
        "call_cushion": call_cushion,
        "threatened_side": threatened_side,
        "short_strike": round(short_strike, 2),
        "short_cushion": short_cushion,
        "one_day_expected_move": round(move, 2),
        "expected_move_source": source,
        "cushion_to_1d_em_ratio": ratio,
    }
