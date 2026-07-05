from datetime import datetime

from bxk_app.market_data import market_data


class MarketEngine:
    def __init__(self):
        self.status = "STOPPED"
        self.last_update = None
        self.last_error = None
        self.source = "placeholder"

    def refresh(self):
        """
        Phase 1B placeholder refresh.
        Later this will pull from Tastytrade first, then Schwab.
        """

        try:
            market_data.update(
                spx=7535.54,
                spx_change=0.00,
                vix=15.85,
                vix1d=12.50,
                expected_move=62.5,
            )

            self.status = "OK"
            self.last_update = datetime.now().isoformat(timespec="seconds")
            self.last_error = None
            self.source = "placeholder"

        except Exception as e:
            self.status = "ERROR"
            self.last_error = str(e)

    def get_status(self):
        return {
            "engine_status": self.status,
            "source": self.source,
            "last_update": self.last_update,
            "last_error": self.last_error,
        }


market_engine = MarketEngine()