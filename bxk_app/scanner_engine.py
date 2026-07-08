from bxk_app.option_scanner import (
    generate_candidate_condors,
    normalize_candidate,
)

from bxk_app.live_option_engine import calculate_iron_condor_credit
from bxk_app.trade_quality import score_candidate
from bxk_app.scanner_settings import scanner_settings


def enrich_candidate(trade: dict) -> dict:
    live = calculate_iron_condor_credit(trade)
    credit = live.get("live_credit", 0)

    wing_width = trade.get("wing_width", scanner_settings.wing_width)

    trade["credit"] = credit
    trade["live_credit"] = credit
    trade["target_credit"] = credit
    trade["put_credit"] = live.get("put_credit", 0)
    trade["call_credit"] = live.get("call_credit", 0)

    trade["sell_put_mid"] = live.get("sell_put_mid", 0)
    trade["buy_put_mid"] = live.get("buy_put_mid", 0)
    trade["sell_call_mid"] = live.get("sell_call_mid", 0)
    trade["buy_call_mid"] = live.get("buy_call_mid", 0)

    trade["max_risk"] = round((wing_width - credit) * 100, 2)
    trade["expected_profit"] = round(credit * 100, 2)

    trade["return_on_risk"] = (
        round((credit / (wing_width - credit)) * 100, 2)
        if credit > 0 and wing_width > credit
        else 0
    )

    trade["pop"] = 85
    trade["score"] = score_candidate(trade)
    trade["trade_score"] = trade["score"]

    return trade


def find_top_iron_condors(
    spx_price: float,
    expected_move: float,
    wing_width: int | None = None,
    limit: int = 10,
    days_to_expiration: int = 0,
) -> list[dict]:

    raw_candidates = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    ranked = []

    for raw in raw_candidates:
        trade = normalize_candidate(
            raw,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        enriched = enrich_candidate(trade)

        if enriched.get("live_credit", 0) < scanner_settings.minimum_credit:
            continue

        ranked.append(enriched)

    ranked.sort(
        key=lambda x: (
            x.get("trade_score", 0),
            x.get("live_credit", 0),
            x.get("return_on_risk", 0),
            x.get("put_buffer", 0),
            x.get("call_buffer", 0),
        ),
        reverse=True,
    )

    return ranked[:limit]


def find_best_iron_condor(
    spx_price: float,
    expected_move: float,
    wing_width: int | None = None,
    days_to_expiration: int = 0,
) -> dict | None:

    top = find_top_iron_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        limit=10,
        days_to_expiration=days_to_expiration,
    )

    if not top:
        return None

    best = dict(top[0])
    best["candidates_evaluated"] = len(top)
    best["top_candidates"] = []

    return best