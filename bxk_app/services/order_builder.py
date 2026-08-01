def build_order(best_trade, quantity=1):
    """
    Build a broker-independent order object from
    the selected BXK trade.
    """

    if not best_trade:
        raise ValueError(
            "No trade supplied."
        )

    return {
        "strategy": best_trade.get(
            "strategy",
            "Unknown",
        ),

        "symbol": best_trade.get(
            "symbol",
            "SPX",
        ),

        "expiration": best_trade.get(
            "expiration",
        ),

        "quantity": quantity,

        "order_type": "LIMIT",

        "time_in_force": "DAY",

        "limit_price": best_trade.get(
            "credit",
            0,
        ),

        "buying_power": best_trade.get(
            "max_risk",
            0,
        ),

        "max_risk": best_trade.get(
            "max_risk",
            0,
        ),

        "max_profit": best_trade.get(
            "max_profit",
            0,
        ),

        "legs": [

            {
                "action": "SELL",
                "option_type": "PUT",
                "strike": best_trade.get(
                    "sell_put",
                ),
                "symbol": best_trade.get(
                    "sell_put_symbol",
                ),
            },

            {
                "action": "BUY",
                "option_type": "PUT",
                "strike": best_trade.get(
                    "buy_put",
                ),
                "symbol": best_trade.get(
                    "buy_put_symbol",
                ),
            },

            {
                "action": "SELL",
                "option_type": "CALL",
                "strike": best_trade.get(
                    "sell_call",
                ),
                "symbol": best_trade.get(
                    "sell_call_symbol",
                ),
            },

            {
                "action": "BUY",
                "option_type": "CALL",
                "strike": best_trade.get(
                    "buy_call",
                ),
                "symbol": best_trade.get(
                    "buy_call_symbol",
                ),
            },

        ],
    }