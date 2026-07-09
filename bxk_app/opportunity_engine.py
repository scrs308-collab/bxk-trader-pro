from bxk_app.models import MarketDecision
from bxk_app.market_data import market_data
from bxk_app.wing_optimizer import find_best_trade

def round_to_5(value: float) -> int:
    return int(round(value / 5) * 5)


def calculate_trade_score(
    target_credit: float,
    wing_width: int,
    put_buffer: float,
    call_buffer: float,
    expected_move: float,
) -> int:
    score = 100

    if target_credit < 1.50:
        score -= 20

    if wing_width > 25:
        score -= 10

    if put_buffer < expected_move:
        score -= 20

    if call_buffer < expected_move:
        score -= 20

    return max(0, min(100, score))


def confidence_from_score(score: int) -> str:
    if score >= 90:
        return "HIGH"
    if score >= 75:
        return "MEDIUM"
    return "LOW"

def build_opportunity(market: MarketDecision) -> dict:
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
            "source": "NONE",
            "spx_price": round(spx_price, 2) if spx_price else None,
            "expected_move": round(expected_move, 2) if expected_move else None,
            "sell_put": None,
            "sell_call": None,
            "buy_put": None,
            "buy_call": None,
            "target_credit": None,
            "live_credit": None,
            "put_credit": None,
            "call_credit": None,
            "pop": None,
            "risk_level": "WAIT",
            "trade_score": 0,
            "confidence": "WAIT",
            "max_risk": None,
            "expected_profit": None,
            "reasons": market.reasons,
        }

    wing_width = 25
    target_credit = 1.75
    fallback_reason = None

    chain_trade = None

    if chain_trade:
        source = chain_trade.get("source", "LIVE_CHAIN_RANKED")
        target_credit = chain_trade.get("live_credit", target_credit)
        wing_width = chain_trade.get("wing_width", wing_width)

        sell_put = chain_trade["sell_put"]
        buy_put = chain_trade["buy_put"]
        sell_call = chain_trade["sell_call"]
        buy_call = chain_trade["buy_call"]
        put_buffer = chain_trade["put_buffer"]
        call_buffer = chain_trade["call_buffer"]
        put_credit = chain_trade.get("put_credit")
        call_credit = chain_trade.get("call_credit")
        days_to_expiration = chain_trade.get("days_to_expiration")
    else:
        source = "ESTIMATE"
        fallback_reason = "Live chain rejected or unavailable: using estimated 25-point IC."

        sell_put = round_to_5(spx_price - expected_move)
        sell_call = round_to_5(spx_price + expected_move)
        buy_put = sell_put - wing_width
        buy_call = sell_call + wing_width
        put_buffer = round(spx_price - sell_put, 2)
        call_buffer = round(sell_call - spx_price, 2)
        put_credit = None
        call_credit = None
        days_to_expiration = 0

    max_risk = round((wing_width - target_credit) * 100, 2)
    expected_profit = round(target_credit * 100, 2)

    trade_score = calculate_trade_score(
        target_credit=target_credit,
        wing_width=wing_width,
        put_buffer=put_buffer,
        call_buffer=call_buffer,
        expected_move=expected_move,
    )

    confidence = confidence_from_score(trade_score)

    reasons = list(market.reasons)

    if fallback_reason:
        reasons.append(fallback_reason)

    reasons.extend(
        [
            f"Source: {source}",
            f"SPX price: {round(spx_price, 2)}",
            f"Expected move: ±{round(expected_move, 2)}",
            f"Put buffer: {put_buffer}",
            f"Call buffer: {call_buffer}",
            f"{wing_width}-point wings selected",
            f"Target credit: {target_credit}",
        ]
    )

    return {
        "strategy": "IRON CONDOR",
        "source": source,
        "days_to_expiration": days_to_expiration,
        "spx_price": round(spx_price, 2),
        "expected_move": round(expected_move, 2),
        "sell_put": sell_put,
        "sell_call": sell_call,
        "buy_put": buy_put,
        "buy_call": buy_call,
        "target_credit": target_credit,
        "live_credit": target_credit,
        "put_credit": put_credit,
        "call_credit": call_credit,
        "pop": 85,
        "risk_level": "LOW" if trade_score >= 75 else "MEDIUM",
        "trade_score": trade_score,
        "confidence": confidence,
        "put_buffer": put_buffer,
        "call_buffer": call_buffer,
        "max_risk": max_risk,
        "expected_profit": expected_profit,
        "reasons": reasons,
    }
