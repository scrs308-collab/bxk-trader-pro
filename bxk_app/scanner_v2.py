from bxk_app.option_scanner import generate_candidate_condors, normalize_candidate
from bxk_app.quote_cache import quote_cache
from bxk_app.live_option_engine import calculate_iron_condor_credit_from_quotes


def score_v2(trade: dict) -> int:
    score = 100

    if trade.get("live_credit", 0) < 1.00:
        score -= 30

    if trade.get("put_credit", 0) <= 0:
        score -= 40

    if trade.get("call_credit", 0) <= 0:
        score -= 40

    if trade.get("put_buffer", 0) < trade.get("expected_move", 0):
        score -= 15

    if trade.get("call_buffer", 0) < trade.get("expected_move", 0):
        score -= 15

    return max(0, min(100, score))


def find_best_iron_condor_v2(
    spx_price: float,
    expected_move: float,
    wing_width: int = 25,
    days_to_expiration: int = 1,
):
    raw_candidates = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    evaluated = []
    rejected = []

    for raw in raw_candidates:
        trade = normalize_candidate(
            raw,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        live = calculate_iron_condor_credit_from_quotes(
            trade,
            quote_cache.quotes,
        )

        trade.update(live)

        credit = trade.get("live_credit", 0)

        trade["target_credit"] = credit
        trade["max_risk"] = round((wing_width - credit) * 100, 2)
        trade["expected_profit"] = round(credit * 100, 2)
        trade["return_on_risk"] = (
            round((credit / (wing_width - credit)) * 100, 2)
            if credit > 0 and wing_width > credit
            else 0
        )

        trade["trade_score"] = score_v2(trade)

        if not trade.get("valid_credit"):
            trade["reject_reason"] = "Invalid or incomplete live credit"
            rejected.append(trade)
            continue

        if trade["trade_score"] < 50:
            trade["reject_reason"] = "Trade score too low"
            rejected.append(trade)
            continue

        evaluated.append(trade)

    evaluated.sort(
        key=lambda x: (
            x.get("trade_score", 0),
            x.get("live_credit", 0),
            x.get("return_on_risk", 0),
        ),
        reverse=True,
    )

    if not evaluated:
        return {
            "best_trade": None,
            "evaluated_count": 0,
            "rejected_count": len(rejected),
            "rejected": rejected,
        }

    best = evaluated[0]
    best["source"] = "SCANNER_V2_CACHE"
    best["evaluated_count"] = len(evaluated)
    best["rejected_count"] = len(rejected)

    return {
        "best_trade": best,
        "evaluated_count": len(evaluated),
        "rejected_count": len(rejected),
        "rejected": rejected,
    }