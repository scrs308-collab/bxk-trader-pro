import asyncio
from decimal import Decimal

from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Quote

from bxk_app.config import (
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)


def to_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except Exception:
        return default


async def fetch_live_quotes(symbols: list[str]) -> dict:
    session = Session(
        TASTYTRADE_CLIENT_SECRET,
        TASTYTRADE_REFRESH_TOKEN,
    )

    quotes = {}

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, symbols)

        attempts = 0
        max_attempts = len(symbols) * 5

        while len(quotes) < len(symbols) and attempts < max_attempts:
            attempts += 1
            quote = await streamer.get_event(Quote)

            symbol = getattr(quote, "event_symbol", None)

            if not symbol:
                continue

            quotes[symbol] = {
                "bid": to_float(getattr(quote, "bid_price", 0)),
                "ask": to_float(getattr(quote, "ask_price", 0)),
                "bid_size": to_float(getattr(quote, "bid_size", 0)),
                "ask_size": to_float(getattr(quote, "ask_size", 0)),
            }

    return quotes


def get_live_quotes(symbols: list[str]) -> dict:
    try:
        return asyncio.run(fetch_live_quotes(symbols))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(fetch_live_quotes(symbols))
        finally:
            loop.close()
    except Exception as e:
        print(f"LIVE QUOTE ERROR: {e}")
        return {}        
    

def mid_price(quote: dict) -> float:
    bid = to_float(quote.get("bid"))
    ask = to_float(quote.get("ask"))

    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)

    return max(bid, ask, 0)


def calculate_iron_condor_credit(trade: dict) -> dict:
    symbols = [
        trade["sell_put_streamer"],
        trade["buy_put_streamer"],
        trade["sell_call_streamer"],
        trade["buy_call_streamer"],
    ]

    quotes = get_live_quotes(symbols)

    sell_put = quotes.get(trade["sell_put_streamer"], {})
    buy_put = quotes.get(trade["buy_put_streamer"], {})
    sell_call = quotes.get(trade["sell_call_streamer"], {})
    buy_call = quotes.get(trade["buy_call_streamer"], {})

    sell_put_mid = mid_price(sell_put)
    buy_put_mid = mid_price(buy_put)
    sell_call_mid = mid_price(sell_call)
    buy_call_mid = mid_price(buy_call)

    put_credit = sell_put_mid - buy_put_mid
    call_credit = sell_call_mid - buy_call_mid

    total_credit = round(put_credit + call_credit, 2)

    return {
        "live_credit": round(max(total_credit, 0), 2),
        "put_credit": round(put_credit, 2),
        "call_credit": round(call_credit, 2),
        "sell_put_mid": sell_put_mid,
        "buy_put_mid": buy_put_mid,
        "sell_call_mid": sell_call_mid,
        "buy_call_mid": buy_call_mid,
        "quotes": quotes,
    }