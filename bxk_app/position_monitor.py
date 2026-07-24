from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bxk_app.position_coach import evaluate_position


OPTION_PATTERN = re.compile(
    r"^(?P<root>[A-Z]+)\s+"
    r"(?P<date>\d{6})"
    r"(?P<option_type>[CP])"
    r"(?P<strike>\d{8})$"
)


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def parse_option_symbol(
    symbol: str,
) -> dict | None:
    """
    Parse a Tastytrade OCC-style option symbol.

    Example:
        SPXW  260713P07495000
    """

    match = OPTION_PATTERN.match(
        str(symbol or "").strip()
    )

    if not match:
        return None

    raw_date = match.group("date")

    expiration = datetime.strptime(
        raw_date,
        "%y%m%d",
    ).date()

    strike = (
        int(match.group("strike"))
        / 1000
    )

    return {
        "root": match.group("root"),
        "expiration": expiration.isoformat(),
        "option_type": match.group(
            "option_type"
        ),
        "strike": strike,
    }


def calculate_leg_pnl(
    direction: str,
    open_price: float,
    current_price: float,
    quantity: float,
    multiplier: float,
) -> float:
    """
    Calculate P/L using position direction.

    Long:
        Current value - opening value

    Short:
        Opening value - current value
    """

    direction_upper = str(
        direction or ""
    ).upper()

    if direction_upper == "SHORT":
        pnl = (
            open_price - current_price
        ) * quantity * multiplier
    else:
        pnl = (
            current_price - open_price
        ) * quantity * multiplier

    return round(pnl, 2)


def days_until_expiration(
    expires_at: str,
) -> int | None:
    if not expires_at:
        return None

    try:
        expiration = datetime.fromisoformat(
            expires_at.replace(
                "Z",
                "+00:00",
            )
        )

        now = datetime.now(
            timezone.utc
        )

        seconds_remaining = (
            expiration - now
        ).total_seconds()

        return max(
            0,
            int(
                seconds_remaining
                // 86400
            ),
        )

    except (TypeError, ValueError):
        return None


def position_status(
    pnl_percent: float,
    put_distance: float | None,
    call_distance: float | None,
    dte: int | None,
) -> tuple[str, str]:
    """
    Assign a simple management status.

    These thresholds can later move into settings.
    """

    if (
        put_distance is None
        or call_distance is None
    ):
        return (
            "DATA WAIT",
            (
                "Current SPX price is unavailable, "
                "so strike-distance risk cannot be evaluated."
            ),
        )

    valid_distances = [
        distance
        for distance in (
            put_distance,
            call_distance,
        )
        if distance is not None
    ]

    nearest_distance = (
        min(valid_distances)
        if valid_distances
        else None
    )

    if pnl_percent >= 50:
        return (
            "TAKE PROFITS",
            "Position has reached the 50% profit target.",
        )

    if pnl_percent <= -100:
        return (
            "EXIT",
            "Position loss has reached the initial credit.",
        )

    if (
        nearest_distance is not None
        and nearest_distance <= 10
    ):
        return (
            "DEFEND",
            "SPX is within 10 points of a short strike.",
        )

    if (
        nearest_distance is not None
        and nearest_distance <= 20
    ):
        return (
            "WARNING",
            "SPX is approaching a short strike.",
        )

    if (
        dte is not None
        and dte == 0
    ):
        return (
            "MANAGE",
            "Position expires today.",
        )

    return (
        "HOLD",
        "Position remains within the normal management range.",
    )


def build_iron_condor_summary(
    positions: list[dict],
    spx_price: float | None = None,
) -> dict | None:
    """
    Group four SPX option legs into one iron condor summary.
    """

    parsed_legs = []

    for position in positions:
        parsed = parse_option_symbol(
            position.get("symbol", "")
        )

        if not parsed:
            continue

        direction = str(
            position.get("direction", ""),
        ).upper()

        quantity = abs(
            safe_float(
                position.get("quantity")
            )
        )

        multiplier = safe_float(
            position.get("multiplier"),
            100,
        )

        open_price = safe_float(
            position.get(
                "average_open_price"
            )
        )

        current_price = safe_float(
            position.get(
                "current_price"
            )
        )

        leg_pnl = calculate_leg_pnl(
            direction=direction,
            open_price=open_price,
            current_price=current_price,
            quantity=quantity,
            multiplier=multiplier,
        )

        parsed_legs.append({
            **parsed,
            "symbol": position.get("symbol"),
            "direction": direction,
            "quantity": quantity,
            "multiplier": multiplier,
            "open_price": open_price,
            "current_price": current_price,
            "price_source": position.get(
                "price_source",
                "close-price",
            ),
            "pnl": leg_pnl,
            "broker_open_pnl": safe_float(
                position.get("pnl")
            ),
            "expires_at": position.get(
                "expires_at"
            ),
        })

    if len(parsed_legs) != 4:
        return None

    long_puts = [
        leg
        for leg in parsed_legs
        if (
            leg["option_type"] == "P"
            and leg["direction"] == "LONG"
        )
    ]

    short_puts = [
        leg
        for leg in parsed_legs
        if (
            leg["option_type"] == "P"
            and leg["direction"] == "SHORT"
        )
    ]

    short_calls = [
        leg
        for leg in parsed_legs
        if (
            leg["option_type"] == "C"
            and leg["direction"] == "SHORT"
        )
    ]

    long_calls = [
        leg
        for leg in parsed_legs
        if (
            leg["option_type"] == "C"
            and leg["direction"] == "LONG"
        )
    ]

    if not all(
        [
            long_puts,
            short_puts,
            short_calls,
            long_calls,
        ]
    ):
        return None

    long_put = long_puts[0]
    short_put = short_puts[0]
    short_call = short_calls[0]
    long_call = long_calls[0]

    quantity = min(
        leg["quantity"]
        for leg in parsed_legs
    )

    broker_open_pnl = sum(
        leg.get(
            "broker_open_pnl",
            0,
        )
        for leg in parsed_legs
    )

    multiplier = short_put["multiplier"]

    opening_credit = (
        short_put["open_price"]
        + short_call["open_price"]
        - long_put["open_price"]
        - long_call["open_price"]
    )

    current_debit = (
        short_put["current_price"]
        + short_call["current_price"]
        - long_put["current_price"]
        - long_call["current_price"]
    )

    pnl = (
        opening_credit - current_debit
    ) * quantity * multiplier

    opening_credit_dollars = (
        opening_credit
        * quantity
        * multiplier
    )

    pnl_percent = (
        pnl
        / opening_credit_dollars
        * 100
        if opening_credit_dollars > 0
        else 0
    )

    put_wing_width = (
        short_put["strike"]
        - long_put["strike"]
    )

    call_wing_width = (
        long_call["strike"]
        - short_call["strike"]
    )

    wing_width = max(
        put_wing_width,
        call_wing_width,
    )

    max_profit = (
        opening_credit
        * quantity
        * multiplier
    )

    max_risk = (
        wing_width - opening_credit
    ) * quantity * multiplier

    put_distance = None
    call_distance = None

    if spx_price is not None and spx_price > 0:
        put_distance = round(
            spx_price
            - short_put["strike"],
            2,
        )

        call_distance = round(
            short_call["strike"]
            - spx_price,
            2,
        )

    expires_at = short_put.get(
        "expires_at"
    )

    dte = days_until_expiration(
        expires_at
    )

    status, recommendation = (
        position_status(
            pnl_percent=pnl_percent,
            put_distance=put_distance,
            call_distance=call_distance,
            dte=dte,
        )
    )

    position_summary = {
        "strategy": "SPX Iron Condor",
        "underlying": "SPX",
        "quantity": int(quantity),
        "expiration": short_put.get(
            "expiration"
        ),
        "expires_at": expires_at,
        "dte": dte,
        "buy_put": long_put["strike"],
        "sell_put": short_put["strike"],
        "sell_call": short_call["strike"],
        "buy_call": long_call["strike"],
        "put_wing_width": int(
            put_wing_width
        ),
        "call_wing_width": int(
            call_wing_width
        ),
        "wing_width": int(
            wing_width
        ),
        "opening_credit": round(
            opening_credit,
            2,
        ),
        "opening_credit_dollars": round(
            opening_credit_dollars,
            2,
        ),
        "current_debit": round(
            current_debit,
            2,
        ),
        "pnl": round(
            broker_open_pnl,
            2,
        ),
        "pnl_percent": round(
            (
                broker_open_pnl
                / opening_credit_dollars
                * 100
            )
            if opening_credit_dollars > 0
            else 0,
            1,
        ),
        "max_profit": round(
            max_profit,
            2,
        ),
        "max_risk": round(
            max_risk,
            2,
        ),
        "spx_price": (
            round(spx_price, 2)
            if spx_price is not None
            else None
        ),
        "put_distance": put_distance,
        "call_distance": call_distance,
        "status": status,
        "recommendation": recommendation,
        "legs": parsed_legs,
    }

    position_summary["coach"] = (
        evaluate_position(
            position_summary
        )
    )

    return position_summary


def build_position_summaries(
    positions: list[dict],
    spx_price: float | None = None,
) -> list[dict]:
    """
    Group raw option legs by root, expiration, and quantity,
    then build one iron-condor summary for each complete
    four-leg group.
    """

    if not positions:
        return []

    grouped_positions: dict[
        tuple[str, str, float],
        list[dict],
    ] = {}

    for position in positions:
        parsed = parse_option_symbol(
            position.get("symbol", "")
        )

        if not parsed:
            continue

        try:
            quantity = abs(
                float(
                    position.get(
                        "quantity",
                        0,
                    )
                    or 0
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            quantity = 0.0

        if quantity <= 0:
            continue

        group_key = (
            parsed["root"],
            parsed["expiration"],
            quantity,
        )

        grouped_positions.setdefault(
            group_key,
            [],
        ).append(position)

    summaries: list[dict] = []

    sorted_groups = sorted(
        grouped_positions.items(),
        key=lambda item: (
            item[0][1],
            item[0][2],
        ),
    )

    for _, grouped_legs in sorted_groups:
        if len(grouped_legs) != 4:
            continue

        summary = build_iron_condor_summary(
            positions=grouped_legs,
            spx_price=spx_price,
        )

        if summary is not None:
            summaries.append(summary)

    return summaries