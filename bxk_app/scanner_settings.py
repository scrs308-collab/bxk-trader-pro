from dataclasses import dataclass


@dataclass
class ScannerSettings:

    # Strategy
    strategy: str = "IRON_CONDOR"

    # Wing selection
    wing_width: int = 25

    # Candidate search
    search_points: int = 30
    strike_increment: int = 5

    # Premium
    minimum_credit: float = 0.01
    target_credit: float = 1.75

    # Trade quality
    minimum_pop: int = 80
    minimum_trade_score: int = 75

    # Delta
    target_delta: float = 0.10
    max_delta: float = 0.15

    # Scanner
    max_candidates: int = 50

    # Liquidity
    minimum_bid_size: int = 1
    minimum_ask_size: int = 1


scanner_settings = ScannerSettings()
