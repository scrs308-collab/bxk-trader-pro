from bxk_app.models import MarketSnapshot

def get_market_snapshot(symbol: str = "SPX") -> MarketSnapshot:
    """
    Temporary placeholder market data.

    Phase 1 goal:
    - Keep backend stable
    - Confirm scoring works
    - Replace this later with real Schwab/Tastytrade API data
    """

    return MarketSnapshot(
        symbol=symbol,
        price=7535.54,
        vix=15.85,
        atr=11.44,
        iv_rank=34.2,
        expected_move=62.5,
    )