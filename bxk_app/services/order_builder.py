from decimal import Decimal, ROUND_FLOOR

def _strategy_key(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _leg(best_trade, action, option_type, strike_key):
    symbol_key = f"{strike_key}_symbol"

    return {
        "action": action,
        "option_type": option_type,
        "strike": best_trade.get(strike_key),
        "symbol": best_trade.get(symbol_key),
    }


CREDIT_INCREMENT = Decimal("0.05")


def _normalize_credit_to_increment(value):
    # Normalize a positive credit down to the nearest
    # broker-valid $0.05 increment.
    try:
        raw_credit = Decimal(str(value))
    except Exception as exc:
        raise ValueError(
            f"Invalid order credit: {value}"
        ) from exc

    if raw_credit <= 0:
        raise ValueError(
            "Order credit must be greater than zero."
        )

    steps = (
        raw_credit / CREDIT_INCREMENT
    ).to_integral_value(
        rounding=ROUND_FLOOR
    )

    normalized = (
        steps * CREDIT_INCREMENT
    ).quantize(Decimal("0.01"))

    if normalized <= 0:
        raise ValueError(
            "Normalized order credit must be "
            "greater than zero."
        )

    return float(normalized)


def build_order(best_trade, quantity=1):
    """
    Build a broker-independent order object from
    the exact BXK trade supplied.
    """

    if not best_trade:
        raise ValueError("No trade supplied.")

    strategy = best_trade.get(
        "strategy",
        "Unknown",
    )

    strategy_key = _strategy_key(strategy)

    if (
        "bear_call" in strategy_key
        or "call_credit_spread" in strategy_key
    ):
        legs = [
            _leg(
                best_trade,
                "SELL",
                "CALL",
                "sell_call",
            ),
            _leg(
                best_trade,
                "BUY",
                "CALL",
                "buy_call",
            ),
        ]

    elif (
        "bull_put" in strategy_key
        or "put_credit_spread" in strategy_key
    ):
        legs = [
            _leg(
                best_trade,
                "SELL",
                "PUT",
                "sell_put",
            ),
            _leg(
                best_trade,
                "BUY",
                "PUT",
                "buy_put",
            ),
        ]

    elif "iron_condor" in strategy_key:
        legs = [
            _leg(
                best_trade,
                "SELL",
                "PUT",
                "sell_put",
            ),
            _leg(
                best_trade,
                "BUY",
                "PUT",
                "buy_put",
            ),
            _leg(
                best_trade,
                "SELL",
                "CALL",
                "sell_call",
            ),
            _leg(
                best_trade,
                "BUY",
                "CALL",
                "buy_call",
            ),
        ]

    else:
        raise ValueError(
            f"Unsupported order strategy: {strategy}"
        )

    missing_legs = [
        leg
        for leg in legs
        if leg.get("strike") is None
        or not leg.get("symbol")
    ]

    if missing_legs:
        raise ValueError(
            "One or more option legs are missing "
            "a strike or option symbol."
        )


    raw_credit = float(
        best_trade.get("credit") or 0
    )

    limit_price = (
        _normalize_credit_to_increment(
            raw_credit
        )
    )

    raw_max_profit = float(
        best_trade.get("max_profit") or 0
    )
    raw_max_risk = float(
        best_trade.get("max_risk") or 0
    )
    raw_buying_power = float(
        best_trade.get(
            "buying_power",
            raw_max_risk,
        )
        or 0
    )

    order_quantity = int(quantity)

    if order_quantity < 1:
        raise ValueError(
            "Order quantity must be greater than zero."
        )

    credit_adjustment_dollars = round(
        (
            raw_credit
            - limit_price
        )
        * 100
        * order_quantity,
        2,
    )

    max_profit = round(
        (
            raw_max_profit
            * order_quantity
        )
        - credit_adjustment_dollars,
        2,
    )

    max_risk = round(
        (
            raw_max_risk
            * order_quantity
        )
        + credit_adjustment_dollars,
        2,
    )

    buying_power = round(
        (
            raw_buying_power
            * order_quantity
        )
        + credit_adjustment_dollars,
        2,
    )

    return {
        "strategy": strategy,
        "symbol": best_trade.get(
            "symbol",
            "SPX",
        ),
        "expiration": best_trade.get(
            "expiration",
        ),
        "dte": best_trade.get("dte"),
        "quantity": order_quantity,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": limit_price,
        "scanner_credit": raw_credit,
        "credit_increment": 0.05,
        "credit_adjustment_dollars": (
            credit_adjustment_dollars
        ),
        "buying_power": buying_power,
        "max_risk": max_risk,
        "max_profit": max_profit,
        "pop": best_trade.get(
            "pop",
            0,
        ),
        "legs": legs,
    }
