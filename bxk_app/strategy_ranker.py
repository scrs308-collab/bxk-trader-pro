from typing import List, Dict


def rank_strategies(market_score: int, trend: str, vix_state: str) -> List[Dict]:
    """
    Early placeholder Strategy Ranking Engine.
    Later this will use live VWAP, option chain, IV, positions, and time of day.
    """

    strategies = []

    # Iron Condor
    ic_score = market_score
    if vix_state == "IDEAL":
        ic_score += 10
    if trend == "MIXED":
        ic_score += 10

    strategies.append({
        "name": "Iron Condor",
        "score": min(ic_score, 100),
        "confidence": "High" if ic_score >= 80 else "Medium" if ic_score >= 60 else "Low",
        "reason": "Best when volatility is healthy and trend is not aggressively directional."
    })

    # Debit Call
    call_score = 35
    if trend == "BULL":
        call_score += 35
    if vix_state == "IDEAL":
        call_score += 10

    strategies.append({
        "name": "Debit Call Spread",
        "score": min(call_score, 100),
        "confidence": "High" if call_score >= 80 else "Medium" if call_score >= 60 else "Low",
        "reason": "Best when trend is bullish and price is not extended."
    })

    # Debit Put
    put_score = 35
    if trend == "BEAR":
        put_score += 35
    if vix_state == "IDEAL":
        put_score += 10

    strategies.append({
        "name": "Debit Put Spread",
        "score": min(put_score, 100),
        "confidence": "High" if put_score >= 80 else "Medium" if put_score >= 60 else "Low",
        "reason": "Best when trend is bearish and downside momentum is confirmed."
    })

    # Butterfly
    fly_score = 50
    if trend == "MIXED":
        fly_score += 20

    strategies.append({
        "name": "Butterfly",
        "score": min(fly_score, 100),
        "confidence": "High" if fly_score >= 80 else "Medium" if fly_score >= 60 else "Low",
        "reason": "Best when price is consolidating near a magnet level."
    })

    # Highest scoring strategy first
    strategies.sort(key=lambda s: s["score"], reverse=True)

    return strategies