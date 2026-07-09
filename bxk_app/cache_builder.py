from bxk_app.option_scanner import generate_candidate_condors, normalize_candidate


def build_symbol_list(
    spx_price: float,
    expected_move: float,
    wing_width: int = 25,
    days_to_expiration: int = 0,
):
    raw = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    symbols = set()

    trades = []

    for candidate in raw:

        trade = normalize_candidate(
            candidate,
            spx_price,
            expected_move,
        )

        trades.append(trade)

        symbols.update([
            trade["sell_put_streamer"],
            trade["buy_put_streamer"],
            trade["sell_call_streamer"],
            trade["buy_call_streamer"],
        ])

    return {
        "symbols": sorted(symbols),
        "trades": trades,
    }