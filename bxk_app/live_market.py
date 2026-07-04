import threading
import time

from bxk_app.market_data import market_data


def calculate_expected_move(spx, vix1d):
    """
    Estimate 1-day SPX expected move using VIX1D.
    Formula: SPX * (VIX1D / 100) / sqrt(252)
    """
    try:
        return spx * (vix1d / 100) / (252 ** 0.5)
    except Exception:
        return None


class LiveMarketEngine:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        while self.running:
            try:
                #
                # Temporary placeholder values.
                # These will be replaced with live Schwab data.
                #
                spx = 6250.15
                spx_change = 12.43
                vix = 16.82
                vix1d = 10.94

                expected_move = calculate_expected_move(spx, vix1d)

                market_data.update(
                    spx=spx,
                    spx_change=spx_change,
                    vix=vix,
                    vix1d=vix1d,
                    expected_move=expected_move,
                )

            except Exception as e:
                print("Market update:", e)

            time.sleep(15)


live_engine = LiveMarketEngine()