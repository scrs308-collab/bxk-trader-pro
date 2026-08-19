from bxk_app.underlyings import (
    UNDERLYINGS,
)
from bxk_app.option_chain_service import (
    get_strikes_by_dte,
    find_nearest_strike,
)
from bxk_app.live_option_engine import (
    calculate_iron_condor_credit,
)


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number <= 0:
        return None

    return number


def _unavailable(
    *,
    symbol,
    reason_code,
    dte,
):
    return {
        "available": False,
        "pricing_ready": False,
        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,
        "underlying": symbol,
        "dte": dte,
        "candidate": None,
        "reason_code": reason_code,
    }


def find_exact_strike(
    target_price,
    strikes,
    tolerance=0.0001,
):
    """
    Find an exact listed strike.

    Long wings must use the requested width exactly.
    Never silently substitute a nearby wing strike.
    """

    target = _positive_float(
        target_price
    )

    if target is None:
        return None

    for item in strikes:
        strike = _positive_float(
            item.get("strike")
        )

        if strike is None:
            continue

        if abs(strike - target) <= tolerance:
            return item

    return None


def _leg_data_complete(*legs):
    for leg in legs:
        if not leg:
            return False

        if not leg.get("call") and not leg.get("put"):
            return False

    return True


def build_underlying_iron_condor(
    symbol,
    underlying_price,
    expected_move,
    *,
    wing_width=None,
    days_to_expiration=0,
):
    """
    Build an underlying-aware iron condor candidate.

    SAFETY:
    - exact requested DTE only
    - exact requested wing width only
    - no execution authorization
    - no SPX fallback
    """

    normalized = str(
        symbol or ""
    ).strip().upper()

    if not normalized:
        return _unavailable(
            symbol="",
            reason_code=(
                "UNDERLYING_SYMBOL_REQUIRED"
            ),
            dte=days_to_expiration,
        )

    # Verified profiles provide known product-specific
    # defaults. They are enrichment, not a whitelist.
    config = UNDERLYINGS.get(
        normalized
    )

    option_chain_symbol = (
        config.option_chain_symbol
        if config is not None
        else normalized
    )

    price = _positive_float(
        underlying_price
    )

    implied_move = _positive_float(
        expected_move
    )

    if price is None:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "UNDERLYING_PRICE_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    if implied_move is None:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "EXPECTED_MOVE_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    if wing_width is None:
        if config is None:
            return _unavailable(
                symbol=normalized,
                reason_code=(
                    "WING_WIDTH_REQUIRED"
                ),
                dte=days_to_expiration,
            )

        wing_width = (
            config.default_wing_width
        )

    width = _positive_float(
        wing_width
    )

    if width is None:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "INVALID_WING_WIDTH"
            ),
            dte=days_to_expiration,
        )

    strikes = get_strikes_by_dte(
        option_chain_symbol,
        days_to_expiration,
    )

    if not strikes:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "OPTION_CHAIN_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    short_put_target = (
        price - implied_move
    )

    short_call_target = (
        price + implied_move
    )

    short_put = find_nearest_strike(
        short_put_target,
        strikes,
    )

    short_call = find_nearest_strike(
        short_call_target,
        strikes,
    )

    if not short_put or not short_call:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "SHORT_STRIKES_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    short_put_strike = float(
        short_put["strike"]
    )

    short_call_strike = float(
        short_call["strike"]
    )

    # A valid iron condor must bracket spot.
    if not (
        short_put_strike
        < price
        < short_call_strike
    ):
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "SHORT_STRIKE_ORDER_INVALID"
            ),
            dte=days_to_expiration,
        )

    long_put_target = (
        short_put_strike - width
    )

    long_call_target = (
        short_call_strike + width
    )

    # Wings are exact, not nearest.
    long_put = find_exact_strike(
        long_put_target,
        strikes,
    )

    long_call = find_exact_strike(
        long_call_target,
        strikes,
    )

    if not long_put or not long_call:
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "EXACT_WING_STRIKES_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    long_put_strike = float(
        long_put["strike"]
    )

    long_call_strike = float(
        long_call["strike"]
    )

    put_width = round(
        short_put_strike
        - long_put_strike,
        4,
    )

    call_width = round(
        long_call_strike
        - short_call_strike,
        4,
    )

    if (
        abs(put_width - width) > 0.0001
        or abs(call_width - width) > 0.0001
    ):
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "WING_WIDTH_MISMATCH"
            ),
            dte=days_to_expiration,
        )

    if not (
        long_put_strike
        < short_put_strike
        < price
        < short_call_strike
        < long_call_strike
    ):
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "CONDOR_STRIKE_ORDER_INVALID"
            ),
            dte=days_to_expiration,
        )

    candidate = {
        "underlying": normalized,
        "strategy": "IRON CONDOR",
        "source": (
            "UNDERLYING_CHAIN_OBSERVATION"
        ),

        "verified_profile": (
            config is not None
        ),

        "option_chain_symbol": (
            option_chain_symbol
        ),

        "underlying_price": round(
            price,
            2,
        ),

        "expected_move": round(
            implied_move,
            2,
        ),

        "expiration": short_put.get(
            "expiration_date"
        ),

        "dte": int(
            short_put.get(
                "days_to_expiration",
                days_to_expiration,
            )
        ),

        "settlement_type": (
            short_put.get(
                "settlement_type"
            )
        ),

        "sell_put": short_put_strike,
        "buy_put": long_put_strike,
        "sell_call": short_call_strike,
        "buy_call": long_call_strike,

        "sell_put_symbol": (
            short_put.get("put")
        ),
        "buy_put_symbol": (
            long_put.get("put")
        ),
        "sell_call_symbol": (
            short_call.get("call")
        ),
        "buy_call_symbol": (
            long_call.get("call")
        ),

        "sell_put_streamer": (
            short_put.get(
                "put_streamer"
            )
        ),
        "buy_put_streamer": (
            long_put.get(
                "put_streamer"
            )
        ),
        "sell_call_streamer": (
            short_call.get(
                "call_streamer"
            )
        ),
        "buy_call_streamer": (
            long_call.get(
                "call_streamer"
            )
        ),

        "put_buffer": round(
            price - short_put_strike,
            2,
        ),

        "call_buffer": round(
            short_call_strike - price,
            2,
        ),

        "requested_wing_width": width,
        "put_wing_width": put_width,
        "call_wing_width": call_width,
        "wing_width": width,
    }

    required_streamers = (
        candidate[
            "sell_put_streamer"
        ],
        candidate[
            "buy_put_streamer"
        ],
        candidate[
            "sell_call_streamer"
        ],
        candidate[
            "buy_call_streamer"
        ],
    )

    if not all(required_streamers):
        return _unavailable(
            symbol=normalized,
            reason_code=(
                "OPTION_STREAMER_SYMBOL_UNAVAILABLE"
            ),
            dte=days_to_expiration,
        )

    return {
        "available": True,
        "pricing_ready": False,
        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,
        "underlying": normalized,
        "dte": days_to_expiration,
        "candidate": candidate,
        "reason_code": (
            "CONDOR_CANDIDATE_AVAILABLE"
        ),
    }


def price_underlying_iron_condor(
    result,
):
    """
    Add live option pricing to an observation-only candidate.

    This still cannot authorize execution.
    """

    if (
        not result
        or result.get("available") is not True
        or not result.get("candidate")
    ):
        return result

    candidate = dict(
        result["candidate"]
    )

    try:
        live = calculate_iron_condor_credit(
            candidate
        )
    except Exception:
        result = dict(result)
        result["pricing_ready"] = False
        result["reason_code"] = (
            "CONDOR_PRICING_ERROR"
        )
        return result

    credit = _positive_float(
        live.get("live_credit")
    )

    width = _positive_float(
        candidate.get("wing_width")
    )

    if credit is None:
        result = dict(result)
        result["pricing_ready"] = False
        result["reason_code"] = (
            "CONDOR_CREDIT_UNAVAILABLE"
        )
        return result

    if width is None or credit >= width:
        result = dict(result)
        result["pricing_ready"] = False
        result["reason_code"] = (
            "CONDOR_ECONOMICS_INVALID"
        )
        return result

    max_profit = round(
        credit * 100,
        2,
    )

    max_risk = round(
        (width - credit) * 100,
        2,
    )

    return_on_risk = round(
        max_profit / max_risk * 100,
        2,
    )

    candidate.update(
        {
            "live_credit": round(
                credit,
                2,
            ),
            "credit": round(
                credit,
                2,
            ),
            "put_credit": live.get(
                "put_credit"
            ),
            "call_credit": live.get(
                "call_credit"
            ),
            "max_profit": max_profit,
            "max_risk": max_risk,
            "return_on_risk": (
                return_on_risk
            ),
        }
    )

    return {
        **result,
        "pricing_ready": True,
        "signal_ready": False,
        "execution_enabled": False,
        "observation_only": True,
        "candidate": candidate,
        "reason_code": (
            "CONDOR_CANDIDATE_PRICED"
        ),
    }


def build_and_price_underlying_condor(
    symbol,
    underlying_price,
    expected_move,
    *,
    wing_width=None,
    days_to_expiration=0,
):
    result = build_underlying_iron_condor(
        symbol,
        underlying_price,
        expected_move,
        wing_width=wing_width,
        days_to_expiration=(
            days_to_expiration
        ),
    )

    return price_underlying_iron_condor(
        result
    )
