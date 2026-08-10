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
        "quantity": int(quantity),
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": best_trade.get(
            "credit",
            0,
        ),
        "buying_power": best_trade.get(
            "buying_power",
            best_trade.get("max_risk", 0),
        ),
        "max_risk": best_trade.get(
            "max_risk",
            0,
        ),
        "max_profit": best_trade.get(
            "max_profit",
            0,
        ),
        "pop": best_trade.get(
            "pop",
            0,
        ),
        "legs": legs,
    }
