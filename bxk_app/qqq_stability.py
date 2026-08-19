def _safe_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number <= 0:
        return None

    return number


def calculate_qqq_stability_metrics(
    *,
    qqq_price,
    expected_move,
    session_open,
    day_high,
    day_low,
    prev_close,
    expected_move_source,
    market_status,
):
    """
    Calculate raw QQQ iron-condor stability measurements.

    This is observation-only.

    QQQ stability becomes ready only when:
      - regular market status is LIVE
      - expected move is derived from the QQQ option chain

    This function does NOT authorize trade execution.
    """

    price = _safe_float(qqq_price)
    implied_move = _safe_float(expected_move)
    open_price = _safe_float(session_open)
    high = _safe_float(day_high)
    low = _safe_float(day_low)

    previous_close = _safe_float(prev_close)

    source = str(
        expected_move_source or ""
    ).strip().upper()

    status = str(
        market_status or ""
    ).strip().upper()

    required = (
        price,
        implied_move,
        open_price,
        high,
        low,
    )

    if not all(required):
        return {
            "available": False,
            "signal_ready": False,
            "state": "UNAVAILABLE",
            "reason_code": (
                "QQQ_STABILITY_DATA_UNAVAILABLE"
            ),
            "expected_move_source": source,
            "market_status": status,
        }

    session_range = max(
        0.0,
        high - low,
    )

    upside_excursion = max(
        0.0,
        high - open_price,
    )

    downside_excursion = max(
        0.0,
        open_price - low,
    )

    max_directional_excursion = max(
        upside_excursion,
        downside_excursion,
    )

    current_displacement = abs(
        price - open_price
    )

    directional_consumed_pct = (
        max_directional_excursion
        / implied_move
        * 100.0
    )

    range_band_consumed_pct = (
        session_range
        / (implied_move * 2.0)
        * 100.0
    )

    current_displacement_pct = (
        current_displacement
        / implied_move
        * 100.0
    )

    overnight_gap = None
    overnight_gap_pct = None

    if previous_close:
        overnight_gap = abs(
            open_price - previous_close
        )

        overnight_gap_pct = (
            overnight_gap
            / implied_move
            * 100.0
        )

    signal_ready = (
        status == "LIVE"
        and source
        == "OPTION_CHAIN_ATM_STRADDLE"
    )

    if status != "LIVE":
        reason_code = "MARKET_NOT_LIVE"

    elif (
        source
        != "OPTION_CHAIN_ATM_STRADDLE"
    ):
        reason_code = (
            "QQQ_OPTION_CHAIN_EM_UNAVAILABLE"
        )

    else:
        reason_code = (
            "QQQ_STABILITY_METRICS_AVAILABLE"
        )

    return {
        "available": True,
        "signal_ready": signal_ready,
        "state": "OBSERVING",
        "reason_code": reason_code,
        "underlying": "QQQ",
        "expected_move_source": source,
        "market_status": status,

        "qqq_price": round(price, 2),
        "session_open": round(
            open_price,
            2,
        ),
        "day_high": round(high, 2),
        "day_low": round(low, 2),

        "prev_close": (
            round(previous_close, 2)
            if previous_close
            else None
        ),

        "implied_move": round(
            implied_move,
            2,
        ),

        "session_range": round(
            session_range,
            2,
        ),

        "upside_excursion": round(
            upside_excursion,
            2,
        ),

        "downside_excursion": round(
            downside_excursion,
            2,
        ),

        "max_directional_excursion": round(
            max_directional_excursion,
            2,
        ),

        "current_displacement": round(
            current_displacement,
            2,
        ),

        "directional_consumed_pct": round(
            directional_consumed_pct,
            1,
        ),

        "range_band_consumed_pct": round(
            range_band_consumed_pct,
            1,
        ),

        "current_displacement_pct": round(
            current_displacement_pct,
            1,
        ),

        "overnight_gap": (
            round(overnight_gap, 2)
            if overnight_gap is not None
            else None
        ),

        "overnight_gap_pct": (
            round(overnight_gap_pct, 1)
            if overnight_gap_pct is not None
            else None
        ),
    }
