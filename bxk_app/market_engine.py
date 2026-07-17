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


class MarketEngine:

    def update(self):

        broker.authenticate()

        spx = broker.get_quote("SPX")
        vix = broker.get_quote("VIX")
        vix1d = broker.get_quote("VIX1D")
        print("\n--- VIX1D QUOTE DEBUG ---")
        print("Raw VIX1D response:", vix1d)
        print("-------------------------\n")
        qqq = broker.get_quote("QQQ")

        account = broker.get_account_summary()
        positions = broker.get_position_summary()

        spx_price = 0.0
        vix_value = 0.0
        vix1d_value = 0.0

        if spx:
            spx_price = float(
                spx.get("last", 0) or 0
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