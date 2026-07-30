from bxk_app.trade_builder import build_best_trade


def rank_strategies():
    """
    Future strategy comparison engine.

    Phase 1:
        Only Iron Condor exists.

    Phase 2:
        Broken Wing Butterfly

    Phase 3:
        Butterfly

    Phase 4:
        Credit Spread

    Phase 5:
        Iron Fly
    """

    strategies = []

    ic = build_best_trade()

    if ic.get("best_trade"):

        trade = ic["best_trade"]

        strategies.append(
            {
                "strategy": "Iron Condor",
                "score": trade["trade_score"],
                "rating": trade["rating"],
                "status": ic["status"],
                "trade": trade,
            }
        )

    strategies.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "best_strategy": strategies[0] if strategies else None,
        "strategies": strategies,
    }