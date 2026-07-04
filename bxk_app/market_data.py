from datetime import datetime


class MarketData:
    def __init__(self):
        self.spx = "--"
        self.spx_change = "--"
        self.vix = "--"
        self.vix1d = "--"
        self.expected_move = "--"

    def market_status(self):
        now = datetime.now()

        if now.weekday() >= 5:
            return "CLOSED"

        minutes = now.hour * 60 + now.minute

        if 570 <= minutes < 960:
            return "LIVE"

        if minutes < 570:
            return "PRE-MARKET"

        return "AFTER HOURS"

    def update(self, spx=None, spx_change=None, vix=None, vix1d=None, expected_move=None):
        if spx is not None:
            self.spx = round(float(spx), 2)

        if spx_change is not None:
            self.spx_change = round(float(spx_change), 2)

        if vix is not None:
            self.vix = round(float(vix), 2)

        if vix1d is not None:
            self.vix1d = round(float(vix1d), 2)

        if expected_move is not None:
            self.expected_move = round(float(expected_move), 2)

    def get_header(self):
        return {
            "spx": self.spx,
            "spx_change": self.spx_change,
            "vix": self.vix,
            "vix1d": self.vix1d,
            "expected_move": self.expected_move,
            "market_status": self.market_status(),
            "server_time": datetime.now().strftime("%I:%M:%S %p"),
        }


market_data = MarketData()