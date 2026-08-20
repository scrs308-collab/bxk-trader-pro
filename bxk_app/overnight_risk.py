def _safe_float(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def calculate_overnight_risk(
    *,
    reference_price,
    prior_close,
    long_put,
    short_put,
    short_call,
    long_call,
    quantity,
    opening_credit,
    reference_source="UNKNOWN",
    market_status="UNKNOWN",
    dte=None,
    timestamp=None,
):
    """
    Calculate observation-only overnight SPX iron-condor risk.

    This function does NOT submit, authorize, modify, or cancel orders.

    State thresholds are provisional and intended for calibration
    against logged real-world overnight sessions.

    States:
      GREEN    < 35% of original threatened-side cushion consumed
      YELLOW   35% to < 60%
      ORANGE   60% to < 80%
      RED      80% to < 100%
      CRITICAL short strike breached or worse
    """

    price = _safe_float(reference_price)
    close = _safe_float(prior_close)

    lp = _safe_float(long_put)
    sp = _safe_float(short_put)
    sc = _safe_float(short_call)
    lc = _safe_float(long_call)

    qty = _safe_int(quantity)
    credit = _safe_float(opening_credit)

    source = str(reference_source or "UNKNOWN").upper()
    status = str(market_status or "UNKNOWN").upper()

    required = (
        price,
        close,
        lp,
        sp,
        sc,
        lc,
        qty,
        credit,
    )

    if not all(required):
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "recommendation": "NONE",
            "reason_code": "OVERNIGHT_RISK_DATA_UNAVAILABLE",
            "reference_source": source,
            "market_status": status,
        }

    if not (lp < sp < sc < lc):
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "recommendation": "NONE",
            "reason_code": "INVALID_STRIKE_ORDER",
            "reference_source": source,
            "market_status": status,
        }

    put_width = sp - lp
    call_width = lc - sc
    max_width = max(put_width, call_width)

    max_risk_per_contract = max(
        0.0,
        (max_width - credit) * 100.0,
    )

    max_risk = max_risk_per_contract * qty

    overnight_move = price - close
    overnight_move_pct = (
        overnight_move / close
    ) * 100.0

    put_distance = price - sp
    call_distance = sc - price

    if put_distance <= call_distance:
        threatened_side = "PUT"
        short_strike = sp
        long_strike = lp
        original_cushion = close - sp
        remaining_cushion = price - sp
        short_breached = price <= sp
        long_breached = price <= lp
    else:
        threatened_side = "CALL"
        short_strike = sc
        long_strike = lc
        original_cushion = sc - close
        remaining_cushion = sc - price
        short_breached = price >= sc
        long_breached = price >= lc

    if original_cushion > 0:
        cushion_consumed_pct = (
            (
                original_cushion
                - remaining_cushion
            )
            / original_cushion
        ) * 100.0
    else:
        cushion_consumed_pct = 100.0

    if long_breached:
        state = "CRITICAL"
        recommendation = "EXIT_REVIEW"
        reason_code = "LONG_STRIKE_BREACHED"

    elif short_breached:
        state = "CRITICAL"
        recommendation = "EXIT_REVIEW"
        reason_code = "SHORT_STRIKE_BREACHED"

    elif cushion_consumed_pct >= 80:
        state = "RED"
        recommendation = "EXIT_REVIEW"
        reason_code = "SHORT_STRIKE_IMMINENT"

    elif cushion_consumed_pct >= 60:
        state = "ORANGE"
        recommendation = "REDUCE"
        reason_code = "OVERNIGHT_CUSHION_SEVERELY_REDUCED"

    elif cushion_consumed_pct >= 35:
        state = "YELLOW"
        recommendation = "WATCH"
        reason_code = "OVERNIGHT_CUSHION_REDUCED"

    else:
        state = "GREEN"
        recommendation = "HOLD"
        reason_code = "OVERNIGHT_RISK_NORMAL"

    return {
        "available": True,
        "observation_only": True,
        "execution_authorized": False,

        "state": state,
        "recommendation": recommendation,
        "reason_code": reason_code,

        "reference_source": source,
        "reference_price": round(price, 2),
        "prior_close": round(close, 2),
        "market_status": status,
        "timestamp": timestamp,
        "dte": dte,

        "overnight_move": round(
            overnight_move,
            2,
        ),
        "overnight_move_pct": round(
            overnight_move_pct,
            2,
        ),

        "threatened_side": threatened_side,

        "long_put": round(lp, 2),
        "short_put": round(sp, 2),
        "short_call": round(sc, 2),
        "long_call": round(lc, 2),

        "short_strike": round(
            short_strike,
            2,
        ),
        "long_strike": round(
            long_strike,
            2,
        ),

        "put_width": round(
            put_width,
            2,
        ),
        "call_width": round(
            call_width,
            2,
        ),

        "original_cushion": round(
            original_cushion,
            2,
        ),
        "remaining_cushion": round(
            remaining_cushion,
            2,
        ),
        "cushion_consumed_pct": round(
            cushion_consumed_pct,
            1,
        ),

        "short_strike_breached":
            short_breached,

        "long_strike_breached":
            long_breached,

        "quantity": qty,
        "opening_credit": round(
            credit,
            2,
        ),

        "max_risk_per_contract": round(
            max_risk_per_contract,
            2,
        ),
        "max_risk": round(
            max_risk,
            2,
        ),
    }
