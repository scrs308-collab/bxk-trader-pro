from datetime import datetime

from bxk_app.live_option_engine import get_live_quotes


class QuoteCache:
    def __init__(self):
        self.quotes = {}
        self.last_updated = None
        self.last_symbols = []
        self.last_error = None

    def refresh(self, symbols: list[str]) -> dict:
        try:
            symbols = [s for s in symbols if s]

            if not symbols:
                self.last_error = "No symbols provided"
                return {}

            self.last_symbols = symbols
            self.quotes = get_live_quotes(symbols)
            self.last_updated = datetime.now().isoformat(timespec="seconds")
            self.last_error = None

            return self.quotes

        except Exception as e:
            self.last_error = str(e)
            return {}

    def get(self, symbol: str) -> dict:
        return self.quotes.get(symbol, {})

    def get_many(self, symbols: list[str]) -> dict:
        return {
            symbol: self.quotes.get(symbol, {})
            for symbol in symbols
        }

    def status(self) -> dict:
        return {
            "quote_count": len(self.quotes),
            "last_updated": self.last_updated,
            "last_error": self.last_error,
            "last_symbols": self.last_symbols,
        }


quote_cache = QuoteCache()