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
def _build_universal_leg(
    position: dict,
) -> dict | None:
    """
    Normalize one broker option leg for vertical/single
    position summaries.
    """

    parsed = parse_option_symbol(
        position.get("symbol", "")
    )

    if not parsed:
        return None

    direction = str(
        position.get("direction", "")
    ).upper()

    if direction not in {
        "LONG",
        "SHORT",
    }:
        return None

    quantity = abs(
        safe_float(
            position.get("quantity")
        )
    )

    if quantity <= 0:
        return None

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

    calculated_pnl = calculate_leg_pnl(
        direction=direction,
        open_price=open_price,
        current_price=current_price,
        quantity=quantity,
        multiplier=multiplier,
    )

    broker_pnl_raw = position.get("pnl")

    has_broker_pnl = (
        broker_pnl_raw is not None
        and str(broker_pnl_raw).strip()
        != ""
    )

    broker_open_pnl = (
        safe_float(broker_pnl_raw)
        if has_broker_pnl
        else calculated_pnl
    )

    return {
        **parsed,
        "symbol": position.get("symbol"),
        "direction": direction,
        "quantity": quantity,
        "multiplier": multiplier,
        "open_price": open_price,
        "current_price": current_price,
        "bid": safe_float(
            position.get("bid")
        ),
        "ask": safe_float(
            position.get("ask")
        ),
        "price_source": position.get(
            "price_source",
            "close-price",
        ),
        "quote_quality": position.get(
            "quote_quality"
        ),
        "quote_reliable": position.get(
            "quote_reliable"
        ),
        "quote_spread": position.get(
            "quote_spread"
        ),
        "quote_spread_pct": position.get(
            "quote_spread_pct"
        ),
        "quote_issue": position.get(
            "quote_issue"
        ),
        "pnl": calculated_pnl,
        "broker_open_pnl": (
            broker_open_pnl
        ),
        "has_broker_pnl": (
            has_broker_pnl
        ),
        "expires_at": position.get(
            "expires_at"
        ),
    }


def _universal_position_status(
    pnl_percent: float,
    dte: int | None,
    short_distance: float | None = None,
    credit_position: bool = False,
) -> tuple[str, str]:
    """
    Management state for non-Iron-Condor positions.
    """

    if (
        credit_position
        and short_distance is not None
        and short_distance <= 10
    ):
        return (
            "DEFEND",
            (
                "SPX is within 10 points "
                "of the short strike."
            ),
        )

    if (
        credit_position
        and short_distance is not None
        and short_distance <= 20
    ):
        return (
            "WARNING",
            (
                "SPX is approaching "
                "the short strike."
            ),
        )

    if pnl_percent >= 50:
        return (
            "TAKE PROFITS",
            (
                "Position has reached "
                "the 50% profit level."
            ),
        )

    if pnl_percent <= -100:
        return (
            "REVIEW",
            (
                "Position loss requires "
                "active review."
            ),
        )

    if dte == 0:
        return (
            "MANAGE",
            "Position expires today.",
        )

    return (
        "HOLD",
        (
            "Position remains within "
            "the normal management range."
        ),
    )


def build_vertical_summary(
    positions: list[dict],
    spx_price: float | None = None,
) -> dict | None:
    """
    Build one two-leg SPX vertical spread summary.
    """

    if len(positions) != 2:
        return None

    parsed_legs = [
        _build_universal_leg(position)
        for position in positions
    ]

    if any(
        leg is None
        for leg in parsed_legs
    ):
        return None

    legs = [
        leg
        for leg in parsed_legs
        if leg is not None
    ]

    option_types = {
        leg["option_type"]
        for leg in legs
    }

    if len(option_types) != 1:
        return None

    long_legs = [
        leg
        for leg in legs
        if leg["direction"] == "LONG"
    ]

    short_legs = [
        leg
        for leg in legs
        if leg["direction"] == "SHORT"
    ]

    if (
        len(long_legs) != 1
        or len(short_legs) != 1
    ):
        return None

    long_leg = long_legs[0]
    short_leg = short_legs[0]

    option_type = long_leg[
        "option_type"
    ]

    quantity = min(
        long_leg["quantity"],
        short_leg["quantity"],
    )

    multiplier = short_leg[
        "multiplier"
    ]

    width = abs(
        short_leg["strike"]
        - long_leg["strike"]
    )

    opening_net_credit = (
        short_leg["open_price"]
        - long_leg["open_price"]
    )

    current_net_credit = (
        short_leg["current_price"]
        - long_leg["current_price"]
    )

    is_credit = (
        opening_net_credit >= 0
    )

    opening_amount = abs(
        opening_net_credit
    )

    opening_dollars = (
        opening_amount
        * quantity
        * multiplier
    )

    width_dollars = (
        width
        * quantity
        * multiplier
    )

    calculated_pnl = sum(
        leg["pnl"]
        for leg in legs
    )

    broker_pnl = sum(
        leg["broker_open_pnl"]
        for leg in legs
    )

    use_broker_pnl = all(
        leg["has_broker_pnl"]
        for leg in legs
    )

    pnl = (
        broker_pnl
        if use_broker_pnl
        else calculated_pnl
    )

    pnl_percent = (
        pnl
        / opening_dollars
        * 100
        if opening_dollars > 0
        else 0
    )

    if is_credit:
        max_profit = opening_dollars
        max_risk = max(
            width_dollars
            - opening_dollars,
            0,
        )
        spread_kind = "Credit"
    else:
        max_risk = opening_dollars
        max_profit = max(
            width_dollars
            - opening_dollars,
            0,
        )
        spread_kind = "Debit"

    type_label = (
        "Put"
        if option_type == "P"
        else "Call"
    )

    strategy = (
        f"SPX {type_label} "
        f"{spread_kind} Spread"
    )

    expires_at = (
        short_leg.get("expires_at")
        or long_leg.get("expires_at")
    )

    dte = days_until_expiration(
        expires_at
    )

    short_distance = None

    if (
        spx_price is not None
        and spx_price > 0
    ):
        if option_type == "P":
            short_distance = round(
                spx_price
                - short_leg["strike"],
                2,
            )
        else:
            short_distance = round(
                short_leg["strike"]
                - spx_price,
                2,
            )

    status, recommendation = (
        _universal_position_status(
            pnl_percent=pnl_percent,
            dte=dte,
            short_distance=(
                short_distance
            ),
            credit_position=is_credit,
        )
    )

    quantity_value = (
        int(quantity)
        if float(quantity).is_integer()
        else quantity
    )

    summary = {
        "strategy": strategy,
        "position_type": "VERTICAL",
        "spread_type": (
            spread_kind.upper()
        ),
        "option_type": (
            "PUT"
            if option_type == "P"
            else "CALL"
        ),
        "underlying": "SPX",
        "quantity": quantity_value,
        "expiration": short_leg[
            "expiration"
        ],
        "expires_at": expires_at,
        "dte": dte,
        "long_strike": int(
            long_leg["strike"]
        ),
        "short_strike": int(
            short_leg["strike"]
        ),
        "width": int(width),
        "opening_credit": (
            round(
                opening_amount,
                2,
            )
            if is_credit
            else 0.0
        ),
        "opening_debit": (
            round(
                opening_amount,
                2,
            )
            if not is_credit
            else 0.0
        ),
        "opening_credit_dollars": (
            round(
                opening_dollars,
                2,
            )
            if is_credit
            else 0.0
        ),
        "opening_debit_dollars": (
            round(
                opening_dollars,
                2,
            )
            if not is_credit
            else 0.0
        ),
        "current_value": round(
            abs(current_net_credit),
            2,
        ),
        "current_debit": (
            round(
                max(
                    current_net_credit,
                    0,
                ),
                2,
            )
            if is_credit
            else None
        ),
        "pnl": round(
            pnl,
            2,
        ),
        "calculated_pnl": round(
            calculated_pnl,
            2,
        ),
        "pnl_percent": round(
            pnl_percent,
            1,
        ),
        "pnl_is_estimate": (
            not use_broker_pnl
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
            if (
                spx_price is not None
                and spx_price > 0
            )
            else None
        ),
        "short_distance": (
            short_distance
        ),
        "status": status,
        "recommendation": (
            recommendation
        ),
        "price_source": (
            "live-mid"
            if any(
                leg.get(
                    "price_source"
                )
                == "live-mid"
                for leg in legs
            )
            else "close-price"
        ),
        "legs": legs,
    }

    if option_type == "P":
        summary.update({
            "buy_put": int(
                long_leg["strike"]
            ),
            "sell_put": int(
                short_leg["strike"]
            ),
        })
    else:
        summary.update({
            "buy_call": int(
                long_leg["strike"]
            ),
            "sell_call": int(
                short_leg["strike"]
            ),
        })

    return summary


def build_single_option_summary(
    position: dict,
    spx_price: float | None = None,
) -> dict | None:
    """
    Build one long/short SPX call or put summary.
    """

    leg = _build_universal_leg(
        position
    )

    if leg is None:
        return None

    option_label = (
        "Call"
        if leg["option_type"] == "C"
        else "Put"
    )

    direction_label = (
        "Long"
        if leg["direction"] == "LONG"
        else "Short"
    )

    strategy = (
        f"SPX {direction_label} "
        f"{option_label}"
    )

    quantity = leg["quantity"]
    multiplier = leg["multiplier"]

    opening_dollars = (
        leg["open_price"]
        * quantity
        * multiplier
    )

    pnl = (
        leg["broker_open_pnl"]
        if leg["has_broker_pnl"]
        else leg["pnl"]
    )

    pnl_percent = (
        pnl
        / opening_dollars
        * 100
        if opening_dollars > 0
        else 0
    )

    expires_at = leg.get(
        "expires_at"
    )

    dte = days_until_expiration(
        expires_at
    )

    status, recommendation = (
        _universal_position_status(
            pnl_percent=pnl_percent,
            dte=dte,
        )
    )

    quantity_value = (
        int(quantity)
        if float(quantity).is_integer()
        else quantity
    )

    is_long = (
        leg["direction"] == "LONG"
    )

    return {
        "strategy": strategy,
        "position_type": "SINGLE",
        "option_type": (
            "CALL"
            if leg["option_type"] == "C"
            else "PUT"
        ),
        "direction": leg[
            "direction"
        ],
        "underlying": "SPX",
        "quantity": quantity_value,
        "expiration": leg[
            "expiration"
        ],
        "expires_at": expires_at,
        "dte": dte,
        "strike": int(
            leg["strike"]
        ),
        "opening_debit": (
            round(
                leg["open_price"],
                2,
            )
            if is_long
            else 0.0
        ),
        "opening_credit": (
            round(
                leg["open_price"],
                2,
            )
            if not is_long
            else 0.0
        ),
        "current_value": round(
            leg["current_price"],
            2,
        ),
        "pnl": round(
            pnl,
            2,
        ),
        "calculated_pnl": round(
            leg["pnl"],
            2,
        ),
        "pnl_percent": round(
            pnl_percent,
            1,
        ),
        "pnl_is_estimate": (
            not leg[
                "has_broker_pnl"
            ]
        ),
        "max_profit": None,
        "max_risk": (
            round(
                opening_dollars,
                2,
            )
            if is_long
            else None
        ),
        "spx_price": (
            round(spx_price, 2)
            if (
                spx_price is not None
                and spx_price > 0
            )
            else None
        ),
        "status": status,
        "recommendation": (
            recommendation
        ),
        "price_source": leg.get(
            "price_source",
            "close-price",
        ),
        "legs": [leg],
    }


def build_position_summaries(
    positions: list[dict],
    spx_price: float | None = None,
) -> list[dict]:
    """
    Build all supported open SPX position summaries.

    Priority:
    1. Preserve valid Iron Condors.
    2. Build two-leg vertical spreads.
    3. Preserve unmatched legs as single options.

    An open parseable SPX option position should never
    disappear merely because it is not an Iron Condor.
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

        quantity = abs(
            safe_float(
                position.get("quantity")
            )
        )

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

        remaining = list(
            grouped_legs
        )

        # First preserve the existing Iron Condor
        # behavior whenever a complete 4-leg group
        # can be recognized.
        if len(remaining) == 4:
            condor = (
                build_iron_condor_summary(
                    positions=remaining,
                    spx_price=spx_price,
                )
            )

            if condor is not None:
                condor.setdefault(
                    "position_type",
                    "IRON_CONDOR",
                )
                summaries.append(
                    condor
                )
                continue

        # Preserve multiple consecutive Iron
        # Condors of the same expiration/quantity.
        if (
            len(remaining) > 4
            and len(remaining) % 4 == 0
        ):
            possible_condors = []
            valid_blocks = True

            for index in range(
                0,
                len(remaining),
                4,
            ):
                block = remaining[
                    index:index + 4
                ]

                condor = (
                    build_iron_condor_summary(
                        positions=block,
                        spx_price=spx_price,
                    )
                )

                if condor is None:
                    valid_blocks = False
                    break

                condor.setdefault(
                    "position_type",
                    "IRON_CONDOR",
                )

                possible_condors.append(
                    condor
                )

            if valid_blocks:
                summaries.extend(
                    possible_condors
                )
                continue

        parsed_remaining = []

        for position in remaining:
            parsed = (
                _build_universal_leg(
                    position
                )
            )

            if parsed is None:
                continue

            parsed_remaining.append({
                "raw": position,
                "parsed": parsed,
            })

        used: set[int] = set()

        # Pair the nearest long/short strikes
        # of the same option type into verticals.
        for option_type in (
            "P",
            "C",
        ):
            short_indexes = [
                index
                for index, item
                in enumerate(
                    parsed_remaining
                )
                if (
                    item["parsed"][
                        "option_type"
                    ]
                    == option_type
                    and item["parsed"][
                        "direction"
                    ]
                    == "SHORT"
                )
            ]

            short_indexes.sort(
                key=lambda index:
                    parsed_remaining[
                        index
                    ]["parsed"]["strike"]
            )

            for short_index in (
                short_indexes
            ):
                if short_index in used:
                    continue

                long_indexes = [
                    index
                    for index, item
                    in enumerate(
                        parsed_remaining
                    )
                    if (
                        index not in used
                        and index
                        != short_index
                        and item[
                            "parsed"
                        ][
                            "option_type"
                        ]
                        == option_type
                        and item[
                            "parsed"
                        ][
                            "direction"
                        ]
                        == "LONG"
                    )
                ]

                if not long_indexes:
                    continue

                short_strike = (
                    parsed_remaining[
                        short_index
                    ]["parsed"]["strike"]
                )

                long_index = min(
                    long_indexes,
                    key=lambda index: abs(
                        parsed_remaining[
                            index
                        ][
                            "parsed"
                        ][
                            "strike"
                        ]
                        - short_strike
                    ),
                )

                vertical = (
                    build_vertical_summary(
                        positions=[
                            parsed_remaining[
                                short_index
                            ]["raw"],
                            parsed_remaining[
                                long_index
                            ]["raw"],
                        ],
                        spx_price=spx_price,
                    )
                )

                if vertical is None:
                    continue

                summaries.append(
                    vertical
                )

                used.add(
                    short_index
                )

                used.add(
                    long_index
                )

        # Anything still unmatched is a real
        # open option position, so display it.
        for index, item in enumerate(
            parsed_remaining
        ):
            if index in used:
                continue

            single = (
                build_single_option_summary(
                    position=item["raw"],
                    spx_price=spx_price,
                )
            )

            if single is not None:
                summaries.append(
                    single
                )

    return summaries
