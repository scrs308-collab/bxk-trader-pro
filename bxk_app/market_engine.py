from bxk_app.market_data import market_data
from bxk_app.brokers.tastytrade import broker


class MarketEngine:

    def update(self):

        broker.authenticate()

        spx = broker.get_quote("SPX")
        vix = broker.get_quote("VIX")
        qqq = broker.get_quote("QQQ")

        account = broker.get_account_summary()
        positions = broker.get_position_summary()

        if spx:
            market_data.update(
                spx=spx.get("last", 0)
            )

        if vix:
            market_data.update(
                vix=vix.get("last", 0)
            )

        market_data.account = account
        market_data.positions = positions
        market_data.qqq = qqq

        return market_data.get_header()


market_engine = MarketEngine()