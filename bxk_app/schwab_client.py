from bxk_app.models import MarketSnapshot


def get_market_snapshot(symbol: str = "SPX") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        price=7535.54,
        vix=15.85,
        atr=11.44,
        iv_rank=34.2,
        expected_move=62.5,
    )