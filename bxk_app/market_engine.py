from math import sqrt

from bxk_app.market_data import market_data
from bxk_app.brokers.tastytrade import broker


def calculate_expected_move(spx_price: float, vix1d_value: float) -> float:
    """
    Estimate the one-trading-day SPX expected move using VIX1D.

    Formula:
        SPX × (VIX1D / 100) ÷ sqrt(252)
    """
    if spx_price <= 0 or vix1d_value <= 0:
        return 0.0

    return round(
        spx_price * (vix1d_value / 100) / sqrt(252),
        2,
    )

def get_quote_price(quote):
    """
    Safely extract a price from a Tastytrade quote.
    """

    if not quote:
        return 0.0

    value = (
        quote.get("last")
        or quote.get("last_price")
        or quote.get("mark")
        or quote.get("mid")
        or 0
    )

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
    
class MarketEngine:

    def update(self, spx=None, vix=None, vix1d=None, account=None, positions=None, qqq=None):

        broker.authenticate()

        spx_price = get_quote_price(spx)
        vix_value = get_quote_price(vix)
        vix1d_value = get_quote_price(vix1d)

        print("SPX QUOTE:", spx)
        print("VIX QUOTE:", vix)
        print("VIX1D QUOTE:", vix1d)

        print(
            "VALUES:",
            {
                "spx": spx_price,
                "vix": vix_value,
                "vix1d": vix1d_value,
            },
        )

        if vix:
            vix_value = float(
                vix.get("last", 0) or 0
            )

        if vix1d:
            vix1d_value = float(
                vix1d.get("last", 0) or 0
            )

        expected_move = calculate_expected_move(
            spx_price,
            vix1d_value,
        )

        market_data.update(
            spx=spx_price,
            vix=vix_value,
            vix1d=vix1d_value,
            expected_move=expected_move,
        )

        market_data.account = account
        market_data.positions = positions
        market_data.qqq = qqq

        return market_data.get_header()


market_engine = MarketEngine()