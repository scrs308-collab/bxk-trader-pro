from bxk_app.models import MarketDecision
from bxk_app.market_data import market_data


def round_to_5(value: float) -> int:
    return int(round(value / 5) * 5)


def build_opportunity(market: MarketDecision) -> dict:
    """
    Builds the trade opportunity object for the dashboard.
    Version 1 estimates SPX iron condor strikes from live snapshot values.
    """

    try:
        snapshot = market_data.get_snapshot()

        spx_price = float(snapshot.get("price", 0))
        expected_move = float(snapshot.get("expected_move", 0))

    except Exception:
        spx_price = 0
        expected_move = 0 
    
    if market.market_regime != "TRADE" or not spx_price or not expected_move:
        return {
            "strategy": "WAIT",
            "sell_put": None,
            "sell_call": None,
            "buy_put": None,
            "buy_call": None,
            "target_credit": None,
            "pop": None,
            "risk_level": "WAIT",
            "expected_profit": None,
            "reasons": market.reasons,
        }

    wing_width = 25

    sell_put = round_to_5(spx_price - expected_move)
    sell_call = round_to_5(spx_price + expected_move)

    buy_put = sell_put - wing_width
    buy_call = sell_call + wing_width

    target_credit = 1.75
    max_risk = (wing_width - target_credit) * 100
    expected_profit = target_credit * 100

    return {
        "strategy": "IRON CONDOR",
        "spx_price": round(spx_price, 2),
        "expected_move": round(expected_move, 2),
        "sell_put": sell_put,
        "sell_call": sell_call,
        "buy_put": buy_put,
        "buy_call": buy_call,
        "target_credit": target_credit,
        "pop": 85,
        "risk_level": "LOW",
        "max_risk": round(max_risk, 2),
        "expected_profit": round(expected_profit, 2),
        "reasons": market.reasons,
    }