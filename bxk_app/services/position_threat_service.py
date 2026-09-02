STATE_RANK = {
    "GREEN": 0,
    "ORANGE": 1,
    "RED": 2,
    "CRITICAL": 3,
}


def _number(value):
    try:
        if value is None:
            return None

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def classify_position_threat(
    position: dict,
):
    """
    Shared daytime short-strike threat classification.

    This is the single source of truth used by both
    SMS alerts and Trade Journal observation.
    """

    if not isinstance(position, dict):
        return None

    spx_price = _number(
        position.get("spx_price")
    )

    put_distance = _number(
        position.get("put_distance")
    )

    call_distance = _number(
        position.get("call_distance")
    )

    short_put = _number(
        position.get("sell_put")
    )

    short_call = _number(
        position.get("sell_call")
    )

    required = (
        spx_price,
        put_distance,
        call_distance,
        short_put,
        short_call,
    )

    if any(
        value is None
        for value in required
    ):
        return None

    if put_distance <= call_distance:
        side = "PUT"
        distance = put_distance
        short_strike = short_put

    else:
        side = "CALL"
        distance = call_distance
        short_strike = short_call

    if distance <= 0:
        state = "CRITICAL"

    elif distance <= 10:
        state = "RED"

    elif distance <= 20:
        state = "ORANGE"

    else:
        state = "GREEN"

    return {
        "state": state,
        "side": side,
        "distance": round(
            distance,
            2,
        ),
        "short_strike":
            short_strike,
        "spx_price": round(
            spx_price,
            2,
        ),
        "put_distance": round(
            put_distance,
            2,
        ),
        "call_distance": round(
            call_distance,
            2,
        ),
        # Preserve the original daytime-alert
        # classifier contract.
        "sell_put": short_put,
        "sell_call": short_call,

        # Aliases are retained for journal/readability
        # without breaking existing consumers.
        "short_put": short_put,
        "short_call": short_call,
        "expiration":
            position.get(
                "expiration"
            ),
    }
