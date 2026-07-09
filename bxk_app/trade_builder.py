from datetime import datetime

from bxk_app.market_data import market_data
from bxk_app.scoring import run_trade_quality
from bxk_app.option_scanner import generate_candidate_condors, normalize_candidate
from bxk_app.live_option_engine import calculate_iron_condor_credit
from bxk_app.trade_analyzer import analyze_trade


def build_demo_trade(spx_price=7535.54, expected_move=62.5, wing_width=25):
    sell_put = round((spx_price - expected_move) / 5) * 5
    buy_put = sell_put - wing_width

    sell_call = round((spx_price + expected_move) / 5) * 5
    buy_call = sell_call + wing_width

    credit = 2.30
    max_profit = round(credit * 100, 2)
    max_risk = round((wing_width - credit) * 100, 2)

    best_trade = {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "dte": 1,
        "spx_price": round(float(spx_price), 2),
        "expected_move": round(float(expected_move), 2),
        "sell_put": sell_put,
        "buy_put": buy_put,
        "sell_call": sell_call,
        "buy_call": buy_call,
        "wing_width": wing_width,
        "credit": credit,
        "max_profit": max_profit,
        "max_risk": max_risk,
        "risk_reward": round(max_risk / max_profit, 2) if max_profit else None,
        "pop": 84,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    analysis = analyze_trade(best_trade)
    best_trade.update(analysis)

    return {
        "status": "DEMO",
        "reason": "Market is closed or live option chain unavailable",
        "best_trade": best_trade,
    }


def build_best_trade(
    wing_width: int = 25,
    days_to_expiration: int = 1,
    min_credit: float = 1.00,
):
    market = run_trade_quality()
    snapshot = market_data.get_snapshot()

    spx_price = snapshot.get("spx") or snapshot.get("price")
    expected_move = snapshot.get("expected_move")

    if not spx_price or float(spx_price) <= 0:
        spx_price = 7535.54

    if not expected_move or float(expected_move) <= 0:
        expected_move = 62.5

    spx_price = float(spx_price)
    expected_move = float(expected_move)

    raw_candidates = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    if not raw_candidates:
        return build_demo_trade(
            spx_price=spx_price,
            expected_move=expected_move,
            wing_width=wing_width,
        )

    ranked = []

    for candidate in raw_candidates:
        trade = normalize_candidate(
            candidate,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        credit_data = calculate_iron_condor_credit(trade)

        credit = credit_data.get("live_credit") or credit_data.get("credit") or 0

        try:
            credit = float(credit)
        except Exception:
            credit = 0

        if credit < min_credit:
            continue

        sell_put = trade["sell_put"]
        buy_put = trade["buy_put"]
        sell_call = trade["sell_call"]
        buy_call = trade["buy_call"]

        max_profit = round(credit * 100, 2)
        max_risk = round((wing_width - credit) * 100, 2)

        put_distance = round(spx_price - sell_put, 2)
        call_distance = round(sell_call - spx_price, 2)

        score = round(
            market.score
            + min(put_distance, call_distance)
            + min(credit * 10, 25),
            2,
        )

        best_candidate = {
            "strategy": "SPX Iron Condor",
            "symbol": "SPX",
            "dte": days_to_expiration,
            "spx_price": round(spx_price, 2),
            "expected_move": round(expected_move, 2),
            "sell_put": sell_put,
            "buy_put": buy_put,
            "sell_call": sell_call,
            "buy_call": buy_call,
            "wing_width": wing_width,
            "credit": round(credit, 2),
            "max_profit": max_profit,
            "max_risk": max_risk,
            "risk_reward": round(max_risk / max_profit, 2) if max_profit else None,
            "put_distance": put_distance,
            "call_distance": call_distance,
            "score": score,
            "pop": 84,
            "market_score": market.score,
            "market_regime": market.market_regime,
            "trend": market.trend,
            "vix_state": market.vix_state,
            "expected_move_state": market.expected_move_state,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "credit_details": credit_data,
        }

        analysis = analyze_trade(best_candidate)
        best_candidate.update(analysis)

        ranked.append(best_candidate)

    if not ranked:
        return build_demo_trade(
            spx_price=spx_price,
            expected_move=expected_move,
            wing_width=wing_width,
        )

    ranked.sort(key=lambda x: x["trade_score"], reverse=True)

    return {
        "status": "OK",
        "best_trade": ranked[0],
        "candidate_count": len(ranked),
        "top_candidates": ranked[:5],
    }