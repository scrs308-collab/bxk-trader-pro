from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bxk_app.position_coach import evaluate_position
from zoneinfo import ZoneInfo


OPTION_PATTERN = re.compile(
    r"^(?P<root>[A-Z]+)\s+"
    r"(?P<date>\d{6})"
    r"(?P<option_type>[CP])"
    r"(?P<strike>\d{8})$"
)


MARKET_TIMEZONE = ZoneInfo("America/New_York")


QUOTE_MAX_ABS_SPREAD = 0.50
QUOTE_MAX_REL_SPREAD = 0.50
QUOTE_CHEAP_ONE_SIDED_ASK = 0.15


def assess_quote_quality(
    bid: float,
    ask: float,
    current_price: float,
) -> dict:
    """
    Determine whether an option quote is reliable enough
    to drive position P/L and automated management rules.

    A very cheap one-sided option is allowed as CAUTION
    because its absolute valuation impact is small.
    """

    bid_value = safe_float(bid)
    ask_value = safe_float(ask)
    current_value = safe_float(current_price)

    if ask_value <= 0:
        return {
            "quote_quality": "UNRELIABLE",
            "quote_reliable": False,
            "quote_spread": None,
            "quote_spread_pct": None,
            "quote_issue": "Missing usable ask quote.",
        }

    if bid_value < 0 or ask_value < bid_value:
        return {
            "quote_quality": "UNRELIABLE",
            "quote_reliable": False,
            "quote_spread": None,
            "quote_spread_pct": None,
            "quote_issue": "Crossed or invalid option market.",
        }

    if bid_value <= 0:
        if ask_value <= QUOTE_CHEAP_ONE_SIDED_ASK:
            return {
                "quote_quality": "CAUTION",
                "quote_reliable": True,
                "quote_spread": round(
                    ask_value,
                    4,
                ),
                "quote_spread_pct": None,
                "quote_issue": (
                    "Cheap option has a one-sided market."
                ),
            }

        return {
            "quote_quality": "UNRELIABLE",
            "quote_reliable": False,
            "quote_spread": round(
                ask_value,
                4,
            ),
            "quote_spread_pct": None,
            "quote_issue": "Option market is one-sided.",
        }

    spread = ask_value - bid_value

    midpoint = (
        (bid_value + ask_value) / 2
        if bid_value > 0 and ask_value > 0
        else current_value
    )

    relative_spread = (
        spread / midpoint
        if midpoint > 0
        else None
    )

    reliable = (
        spread <= QUOTE_MAX_ABS_SPREAD
        or (
            relative_spread is not None
            and relative_spread
            <= QUOTE_MAX_REL_SPREAD
        )
    )

    return {
        "quote_quality": (
            "GOOD"
            if reliable
            else "UNRELIABLE"
        ),
        "quote_reliable": reliable,
        "quote_spread": round(
            spread,
            4,
        ),
        "quote_spread_pct": (
            round(
                relative_spread * 100,
                1,
            )
            if relative_spread is not None
            else None
        ),
        "quote_issue": (
            None
            if reliable
            else "Bid/ask spread is abnormally wide."
        ),
    }

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
    """
    Calculate calendar DTE using the US market date.

    This intentionally matches the scanner's DTE behavior
    so UTC rollover after 8 PM Eastern cannot make an
    expiration appear one day closer than it really is.
    """

    if not expires_at:
        return None

    try:
        expiration = datetime.fromisoformat(
            expires_at.replace(
                "Z",
                "+00:00",
            )
        )

        expiration_date = expiration.astimezone(
            MARKET_TIMEZONE
        ).date()

        market_today = datetime.now(
            MARKET_TIMEZONE
        ).date()

        return max(
            0,
            (
                expiration_date
                - market_today
            ).days,
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

        bid = safe_float(
            position.get("bid")
        )

        ask = safe_float(
            position.get("ask")
        )

        quote_quality = assess_quote_quality(
            bid=bid,
            ask=ask,
            current_price=current_price,
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
            "bid": bid,
            "ask": ask,
            **quote_quality,
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

    valid_strike_order = (
        long_put["strike"]
        < short_put["strike"]
        < short_call["strike"]
        < long_call["strike"]
    )

    if not valid_strike_order:
        return None

    quantity = min(
        leg["quantity"]
        for leg in parsed_legs
    )

    unreliable_legs = [
        leg
        for leg in parsed_legs
        if not leg.get(
            "quote_reliable",
            False,
        )
    ]

    caution_legs = [
        leg
        for leg in parsed_legs
        if (
            leg.get("quote_quality")
            == "CAUTION"
        )
    ]

    def quote_leg_label(
        leg: dict,
    ) -> str:
        option_name = (
            "CALL"
            if leg.get("option_type") == "C"
            else "PUT"
        )

        return (
            f'{leg.get("strike"):g} '
            f'{option_name}'
        )

    unreliable_leg_labels = [
        quote_leg_label(leg)
        for leg in unreliable_legs
    ]

    caution_leg_labels = [
        quote_leg_label(leg)
        for leg in caution_legs
    ]

    valuation_reliable = not bool(
        unreliable_legs
    )

    if unreliable_legs:
        quote_quality = "UNRELIABLE"

        valuation_warning = (
            "Wide or incomplete option quotes detected "
            "on "
            + ", ".join(
                unreliable_leg_labels
            )
            + ". P/L is an estimate and P/L-based "
              "exit guidance is suspended."
        )

    elif caution_legs:
        quote_quality = "CAUTION"

        valuation_warning = (
            "One or more low-value option legs have "
            "thin quotes. Valuation remains usable "
            "but should be monitored."
        )

    else:
        quote_quality = "GOOD"
        valuation_warning = None

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
            pnl_percent=(
                pnl_percent
                if valuation_reliable
                else 0.0
            ),
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
        "quote_quality": quote_quality,
        "valuation_reliable":
            valuation_reliable,
        "pnl_is_estimate":
            not valuation_reliable,
        "valuation_warning":
            valuation_warning,
        "unreliable_legs":
            unreliable_leg_labels,
        "caution_quote_legs":
            caution_leg_labels,
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
    Group multiple open SPX iron condors.

    Tastytrade commonly returns each iron condor as
    four consecutive legs. Positions are first grouped
    by root, expiration, and quantity, then evaluated
    in four-leg blocks.
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

        # A complete Iron Condor requires four legs.
        if len(grouped_legs) < 4:
            continue

        # Process every consecutive four-leg position.
        for index in range(
            0,
            len(grouped_legs),
            4,
        ):
            position_legs = grouped_legs[
                index:index + 4
            ]

            if len(position_legs) != 4:
                continue

            summary = build_iron_condor_summary(
                positions=position_legs,
                spx_price=spx_price,
            )

            if summary is not None:
                summaries.append(summary)

    return summaries
