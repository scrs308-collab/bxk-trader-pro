from bxk_app.underlying_stability import (
    calculate_underlying_stability_metrics,
)


_REASON_MAP = {
    "STABILITY_DATA_UNAVAILABLE":
        "QQQ_STABILITY_DATA_UNAVAILABLE",

    "OPTION_CHAIN_EM_UNAVAILABLE":
        "QQQ_OPTION_CHAIN_EM_UNAVAILABLE",

    "STABILITY_METRICS_AVAILABLE":
        "QQQ_STABILITY_METRICS_AVAILABLE",
}


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
    Backward-compatible QQQ stability wrapper.

    All stability math now lives in the generic
    underlying stability engine.
    """

    result = (
        calculate_underlying_stability_metrics(
            symbol="QQQ",
            underlying_price=qqq_price,
            expected_move=expected_move,
            session_open=session_open,
            day_high=day_high,
            day_low=day_low,
            prev_close=prev_close,
            expected_move_source=(
                expected_move_source
            ),
            market_status=market_status,
        )
    )

    result = dict(result)

    reason = result.get(
        "reason_code"
    )

    result["reason_code"] = (
        _REASON_MAP.get(
            reason,
            reason,
        )
    )

    # Preserve the existing QQQ-specific response field
    # while also allowing the generic underlying_price
    # field to coexist.
    result["qqq_price"] = (
        result.get(
            "underlying_price"
        )
    )

    return result
