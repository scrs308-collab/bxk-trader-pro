from datetime import datetime


class MarketData:

    def __init__(self):
        self.spx = None
        self.spx_change = None
        self.vix = None
        self.vix1d = None
        self.market_status = "LIVE"

    def get_header(self):
        return {
            "spx": self.spx,
            "spx_change": self.spx_change,
            "vix": self.vix,
            "vix1d": self.vix1d,
            "market_status": self.market_status,
            "server_time": datetime.now().strftime("%I:%M:%S %p")
        }


market_data = MarketData()
