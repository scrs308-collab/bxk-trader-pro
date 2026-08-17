def _safe_float(value, default=0.0):
    try:
        number = float(value)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


def calculate_condor_stability_metrics(
    *,
    spx_price,
    expected_move,
    session_open,
    day_high,
    day_low,
    prev_close=None,
    expected_move_source="VIX1D",
    market_status="LIVE",
):
    """
    Calculate raw pre-entry iron-condor stability measurements.

    GREEN/YELLOW/RED decisions are intentionally NOT made here yet.

    signal_ready becomes True when:
      - regular market is LIVE
      - expected move is based on VIX1D or VIX

    VIX1D is the preferred source. VIX may be used as a live fallback
    when VIX1D is unavailable.

    Raw metrics remain available for observation even when signal_ready
    is False.
    """

    price = _safe_float(spx_price)
    implied_move = _safe_float(expected_move)
    open_price = _safe_float(session_open)
    high = _safe_float(day_high)
    low = _safe_float(day_low)
    previous_close = _safe_float(prev_close)

    source = str(expected_move_source or "UNKNOWN").upper()
    status = str(market_status or "UNKNOWN").upper()

    if not all((price, implied_move, open_price, high, low)):
        return {
            "available": False,
            "signal_ready": False,
            "state": "UNAVAILABLE",
            "reason_code": "STABILITY_DATA_UNAVAILABLE",
            "expected_move_source": source,
            "market_status": status,
        }

    session_range = max(0.0, high - low)

    upside_excursion = max(0.0, high - open_price)
    downside_excursion = max(0.0, open_price - low)

    max_directional_excursion = max(
        upside_excursion,
        downside_excursion,
    )

    current_displacement = abs(price - open_price)

    directional_consumed_pct = (
        max_directional_excursion / implied_move
    ) * 100.0

    # expected_move represents one side of the implied band,
    # therefore the entire +/- band is 2 * expected_move.
    range_band_consumed_pct = (
        session_range / (2.0 * implied_move)
    ) * 100.0

    current_displacement_pct = (
        current_displacement / implied_move
    ) * 100.0

    overnight_gap = 0.0
    overnight_gap_pct = 0.0

    if previous_close > 0:
        overnight_gap = abs(open_price - previous_close)
        overnight_gap_pct = (
            overnight_gap / implied_move
        ) * 100.0

    signal_ready = (
        status == "LIVE"
        and source in {"VIX1D", "VIX"}
    )

    if status != "LIVE":
        reason_code = "MARKET_NOT_LIVE"
    elif source == "VIX1D":
        reason_code = "STABILITY_METRICS_AVAILABLE"
    elif source == "VIX":
        reason_code = "VIX_FALLBACK_ACTIVE"
    else:
        reason_code = "EXPECTED_MOVE_SOURCE_UNSUPPORTED"

    return {
        "available": True,
        "signal_ready": signal_ready,
        "state": "OBSERVING",
        "reason_code": reason_code,
        "expected_move_source": source,
        "market_status": status,
        "spx_price": round(price, 2),
        "session_open": round(open_price, 2),
        "day_high": round(high, 2),
        "day_low": round(low, 2),
        "prev_close": (
            round(previous_close, 2)
            if previous_close > 0
            else None
        ),
        "implied_move": round(implied_move, 2),
        "session_range": round(session_range, 2),
        "upside_excursion": round(upside_excursion, 2),
        "downside_excursion": round(downside_excursion, 2),
        "max_directional_excursion": round(
            max_directional_excursion,
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
        "current_displacement": round(
            current_displacement,
            2,
        ),
        "current_displacement_pct": round(
            current_displacement_pct,
            1,
        ),
        "overnight_gap": round(overnight_gap, 2),
        "overnight_gap_pct": round(
            overnight_gap_pct,
            1,
        ),
    }
