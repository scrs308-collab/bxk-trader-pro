from math import sqrt

from bxk_app.condor_stability import (
    calculate_condor_stability_metrics,
)
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

    def update(
        self,
        spx=None,
        vix=None,
        vix1d=None,
        account=None,
        positions=None,
        qqq=None,
    ):
        """
        Fetch live Tastytrade data when values are not supplied,
        then update the shared market-data cache.
        """

        broker.authenticate()

        if spx is None:
            spx = broker.get_quote("SPX")

        if vix is None:
            vix = broker.get_quote("VIX")

        if vix1d is None:
            vix1d = broker.get_quote("$VIX1D")

        if qqq is None:
            qqq = broker.get_quote("QQQ")

        if account is None:
            account = broker.get_account_summary()

        if positions is None:
            positions = broker.get_position_summary()

        spx_price = get_quote_price(spx)
        vix_value = get_quote_price(vix)
        vix1d_value = get_quote_price(vix1d)

        if vix1d_value > 0:
            volatility_value = vix1d_value
            expected_move_source = "VIX1D"
        elif vix_value > 0:
            volatility_value = vix_value
            expected_move_source = "VIX"
        else:
            volatility_value = 0.0
            expected_move_source = "NONE"

        expected_move = calculate_expected_move(spx_price, volatility_value)

        spx_quote = spx if isinstance(spx, dict) else {}

        condor_stability = calculate_condor_stability_metrics(
            spx_price=spx_price,
            expected_move=expected_move,
            session_open=spx_quote.get("open"),
            day_high=spx_quote.get("day-high-price"),
            day_low=spx_quote.get("day-low-price"),
            prev_close=spx_quote.get("prev-close"),
            expected_move_source=expected_move_source,
            market_status=market_data.market_status(),
        )

        market_data.update(
            spx=spx_price,
            vix=vix_value,
            vix1d=vix1d_value,
            expected_move=expected_move,
            condor_stability=condor_stability,
        )

        market_data.account = account or {}
        market_data.positions = positions or []
        market_data.qqq = qqq or {}

        
        return market_data.get_header()


market_engine = MarketEngine()