from __future__ import annotations

from typing import Any


ACTION_STAY = "STAY IN TRADE"
ACTION_CLOSE = "CLOSE POSITION"
ACTION_MONITOR = "INCREASE MONITORING"
ACTION_DEFEND = "PREPARE DEFENSE"
ACTION_DEFEND_NOW = "DEFEND NOW"
ACTION_EXIT = "EXIT POSITION"
ACTION_REVIEW = "REVIEW RISK"


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float without raising an exception.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Convert a value to int without raising an exception.
    """

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_spread_values(
    position: dict,
) -> tuple[float | None, float | None]:
    """
    Calculate the current put-spread and call-spread values
    from the four position legs.

    Expected leg fields:
        option_type
        direction
        current_price
    """

    legs = position.get("legs", [])

    if not isinstance(legs, list):
        return None, None

    long_put = None
    short_put = None
    short_call = None
    long_call = None

    for leg in legs:
        if not isinstance(leg, dict):
            continue

        option_type = str(
            leg.get("option_type", "")
        ).upper()

        direction = str(
            leg.get("direction", "")
        ).upper()

        current_price = safe_float(
            leg.get("current_price")
        )

        if option_type == "P":
            if direction == "LONG":
                long_put = current_price
            elif direction == "SHORT":
                short_put = current_price

        elif option_type == "C":
            if direction == "SHORT":
                short_call = current_price
            elif direction == "LONG":
                long_call = current_price

    put_spread = None
    call_spread = None

    if (
        short_put is not None
        and long_put is not None
    ):
        put_spread = max(
            0.0,
            short_put - long_put,
        )

    if (
        short_call is not None
        and long_call is not None
    ):
        call_spread = max(
            0.0,
            short_call - long_call,
        )

    return put_spread, call_spread


def get_health_rating(
    score: int,
) -> tuple[str, int]:
    """
    Convert a health score into a rating and star count.
    """

    if score >= 90:
        return "Excellent", 5

    if score >= 80:
        return "Good", 4

    if score >= 70:
        return "Fair", 3

    if score >= 60:
        return "Caution", 2

    return "Danger", 1


def evaluate_position(
    position: dict,
) -> dict:
    """
    Evaluate an open SPX iron condor and return
    position-health metrics and coaching guidance.

    The recommendation follows BXK position-management
    rules. Immediate strike risk takes priority over
    profit-taking rules.
    """

    if not isinstance(position, dict) or not position:
        return {
            "health_score": 0,
            "health_rating": "Unavailable",
            "stars": 0,
            "headline": "No open position",
            "recommendation": "NO ACTION",
            "risk_level": "NONE",
            "messages": [
                "No open SPX position was found.",
            ],
            "profit_progress": 0.0,
            "minimum_strike_distance": None,
            "put_spread_value": None,
            "call_spread_value": None,
        }

    pnl = safe_float(
        position.get("pnl")
    )

    pnl_percent = safe_float(
        position.get("pnl_percent")
    )

    max_profit = safe_float(
        position.get("max_profit")
    )

    dte = safe_int(
        position.get("dte")
    )

    put_distance_raw = position.get(
        "put_distance"
    )

    call_distance_raw = position.get(
        "call_distance"
    )

    put_distance = (
        safe_float(put_distance_raw)
        if put_distance_raw is not None
        else None
    )

    call_distance = (
        safe_float(call_distance_raw)
        if call_distance_raw is not None
        else None
    )

    available_distances = [
        distance
        for distance in [
            put_distance,
            call_distance,
        ]
        if distance is not None
    ]

    minimum_distance = (
        min(available_distances)
        if available_distances
        else None
    )

    profit_progress = (
        pnl / max_profit * 100
        if max_profit > 0
        else pnl_percent
    )

    put_spread_value, call_spread_value = (
        get_spread_values(position)
    )

    score = 0
    messages: list[str] = []

    # ==================================================
    # PROFIT PROGRESS — 40 POINTS
    # ==================================================

    if profit_progress >= 75:
        score += 40
        messages.append(
            (
                f"{profit_progress:.1f}% of maximum "
                "profit has been captured."
            )
        )

    elif profit_progress >= 50:
        score += 35
        messages.append(
            (
                f"{profit_progress:.1f}% of maximum "
                "profit has been captured."
            )
        )

    elif profit_progress >= 25:
        score += 20
        messages.append(
            (
                f"Position has captured "
                f"{profit_progress:.1f}% of maximum profit."
            )
        )

    elif profit_progress >= 10:
        score += 10
        messages.append(
            (
                f"Position has captured "
                f"{profit_progress:.1f}% of maximum profit."
            )
        )

    elif profit_progress >= 0:
        messages.append(
            "Position remains below the primary profit target."
        )

    else:
        messages.append(
            (
                f"Position is currently losing "
                f"${abs(pnl):,.2f}."
            )
        )

    # ==================================================
    # STRIKE SAFETY — 30 POINTS
    # ==================================================

    strike_breached = False

    if minimum_distance is None:
        messages.append(
            "Distance to the short strikes is unavailable."
        )

    elif minimum_distance < 0:
        strike_breached = True
        messages.append(
            "SPX has breached a short strike."
        )

    elif minimum_distance > 40:
        score += 30
        messages.append(
            (
                "The nearest short strike is "
                f"{minimum_distance:.1f} points away."
            )
        )

    elif minimum_distance >= 20:
        score += 20
        messages.append(
            (
                "The nearest short strike is "
                f"{minimum_distance:.1f} points away."
            )
        )

    elif minimum_distance >= 10:
        score += 10
        messages.append(
            (
                "The nearest short strike is only "
                f"{minimum_distance:.1f} points away."
            )
        )

    elif minimum_distance >= 5:
        score += 5
        messages.append(
            (
                "SPX is within "
                f"{minimum_distance:.1f} points "
                "of a short strike."
            )
        )

    else:
        messages.append(
            (
                "SPX is dangerously close to a short strike "
                f"at {minimum_distance:.1f} points."
            )
        )

    # ==================================================
    # TIME RISK — 15 POINTS
    # ==================================================

    if dte >= 3:
        score += 15
        messages.append(
            f"Position has {dte} days to expiration."
        )

    elif dte == 2:
        score += 12
        messages.append(
            "Position has two days to expiration."
        )

    elif dte == 1:
        score += 8
        messages.append(
            "Position expires tomorrow."
        )

    else:
        score += 4
        messages.append(
            "Position expires today; gamma risk is elevated."
        )

    # ==================================================
    # PREMIUM DECAY / RISK CONCENTRATION — 15 POINTS
    # ==================================================

    decayed_side = None

    if (
        put_spread_value is not None
        and put_spread_value <= 0.10
    ):
        decayed_side = "put"
        score += 15
        messages.append(
            (
                "The put spread has decayed to "
                f"${put_spread_value:.2f}."
            )
        )

    elif (
        call_spread_value is not None
        and call_spread_value <= 0.10
    ):
        decayed_side = "call"
        score += 15
        messages.append(
            (
                "The call spread has decayed to "
                f"${call_spread_value:.2f}."
            )
        )

    elif (
        put_spread_value is not None
        and call_spread_value is not None
    ):
        messages.append(
            (
                "Both sides of the iron condor retain "
                "meaningful value."
            )
        )

    score = max(
        0,
        min(100, int(round(score))),
    )

    # ==========================================
    # Profit Override
    # A trade that has captured most of its
    # profit should never receive a mediocre
    # health score.
    # ==========================================

    score = max(
    0,
    min(100, int(round(score))),
)

# ==========================================
# PROFIT OVERRIDE
# ==========================================

    if profit_progress >= 75:
        score = max(score, 90)

    elif profit_progress >= 50:
        score = max(score, 80)

    rating, stars = get_health_rating(
        score
)
    # ==================================================
    # RECOMMENDATION
    # Risk rules override profit-taking rules.
    # ==================================================

    if strike_breached:
        recommendation = ACTION_EXIT
        headline = "Short strike breached"
        risk_level = "CRITICAL"

    elif (
        minimum_distance is not None
        and minimum_distance < 5
    ):
        recommendation = ACTION_DEFEND_NOW
        headline = "Short strike in immediate danger"
        risk_level = "HIGH"

    elif (
        minimum_distance is not None
        and minimum_distance < 10
    ):
        recommendation = ACTION_DEFEND
        headline = "Short strike under pressure"
        risk_level = "HIGH"

    elif profit_progress >= 75:
        recommendation = ACTION_CLOSE
        headline = "Strong profit target achieved"
        risk_level = "LOW"

    elif profit_progress >= 50:
        recommendation = ACTION_CLOSE
        headline = "Profit target achieved"
        risk_level = "LOW"

    elif dte == 0 and profit_progress >= 25:
        recommendation = ACTION_CLOSE
        headline = "Expiration-day profit available"
        risk_level = "MODERATE"

    elif dte == 0:
        recommendation = ACTION_MONITOR
        headline = "Expiration-day risk increasing"
        risk_level = "HIGH"

    elif pnl < 0:
        recommendation = ACTION_REVIEW
        headline = "Position needs review"
        risk_level = "MODERATE"

    else:
        recommendation = ACTION_STAY
        headline = "Position remains healthy"
        risk_level = "LOW"

    if decayed_side == "put":
        messages.append(
            "Remaining risk is concentrated on the call side."
        )

    elif decayed_side == "call":
        messages.append(
            "Remaining risk is concentrated on the put side."
        )

    return {
        "health_score": score,
        "health_rating": rating,
        "stars": stars,
        "headline": headline,
        "recommendation": recommendation,
        "risk_level": risk_level,
        "messages": messages,
        "profit_progress": round(
            profit_progress,
            1,
        ),
        "minimum_strike_distance": (
            round(minimum_distance, 2)
            if minimum_distance is not None
            else None
        ),
        "put_spread_value": (
            round(put_spread_value, 2)
            if put_spread_value is not None
            else None
        ),
        "call_spread_value": (
            round(call_spread_value, 2)
            if call_spread_value is not None
            else None
        ),
    }