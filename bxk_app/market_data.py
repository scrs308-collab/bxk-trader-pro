from datetime import datetime


class MarketData:
    def __init__(self):
        self.spx = "--"
        self.spx_change = "--"
        self.vix = "--"
        self.vix1d = "--"
        self.expected_move = "--"
        self.account = {}
        self.positions = []
        self.qqq = {}

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

    def get_snapshot(self):
        """
        Returns backend-safe market snapshot data.
        Used by scoring.py and /api/recommend.
        """

        price = float(self.spx) if self.spx != "--" else 7535.54
        vix = float(self.vix) if self.vix != "--" else 15.85
        vix1d = float(self.vix1d) if self.vix1d != "--" else 14.50
        expected_move = float(self.expected_move) if self.expected_move != "--" else 62.50

        return {
            "symbol": "SPX",
            "price": price,
            "vix": vix,
            "vix1d": vix1d,
            "atr": 0,
            "iv_rank": 25,
            "expected_move": expected_move,
            "market_status": self.market_status(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

    def get_header(self):
        spx_value = float(self.spx) if self.spx != "--" else None
        expected_move_value = float(self.expected_move) if self.expected_move != "--" else None

        short_put = "--"
        short_call = "--"
        wing_width = 25
        long_put = "--"
        long_call = "--"

        if spx_value is not None and expected_move_value is not None:
            lower_move = spx_value - expected_move_value
            upper_move = spx_value + expected_move_value

            short_put = round(lower_move / 5) * 5
            short_call = round(upper_move / 5) * 5

            long_put = short_put - wing_width
            long_call = short_call + wing_width

        return {
            "spx": self.spx,
            "spx_change": self.spx_change,
            "vix": self.vix,
            "vix1d": self.vix1d,
            "expected_move": self.expected_move,
            "short_put": short_put,
            "short_call": short_call,
            "trade_setup": {
                "strategy": "Iron Condor",
                "short_put": short_put,
                "long_put": long_put,
                "short_call": short_call,
                "long_call": long_call,
                "wing_width": wing_width,
                "contracts": 1,
                "target_credit": 2.30,
                "max_profit": 230,
                "max_risk": 2270,
                "risk_reward": "9.9 : 1",
                "pop": 84,
            },
            "market_status": self.market_status(),
            "server_time": datetime.now().strftime("%I:%M:%S %p"),
            "account": self.account,
            "positions": self.positions,
            "qqq": self.qqq,

        }


market_data = MarketData()