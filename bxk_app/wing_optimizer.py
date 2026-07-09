from bxk_app.scanner_engine import find_top_iron_condors

WING_WIDTHS = [5, 10, 20, 25]
DTE_CHOICES = [0, 1, 2, 3]

def find_best_trade(
    spx_price: float,
    expected_move: float,
):
    all_candidates = []

    for dte in DTE_CHOICES:
        for wing in WING_WIDTHS:
            trades = find_top_iron_condors(
                spx_price=spx_price,
                expected_move=expected_move,
                wing_width=wing,
                limit=10,
                days_to_expiration=dte,
            )

            for trade in trades:
                trade["wing_width"] = wing
                trade["days_to_expiration"] = dte
                all_candidates.append(trade)

    all_candidates = [
        trade for trade in all_candidates
        if trade.get("valid_credit") is True
        and trade.get("live_credit", 0) > 0
        and trade.get("put_credit", 0) > 0
        and trade.get("call_credit", 0) > 0
    ]

    if not all_candidates:
        return None

        all_candidates.sort(
            key=lambda t: (
                t.get("trade_score", 0),
                t.get("live_credit", 0),
                t.get("return_on_risk", 0),
            ),
            reverse=True,
        )

        best = dict(all_candidates[0])
        best["candidates_evaluated"] = len(all_candidates)

        # TEMP
        best["top_candidates"] = []

        return best