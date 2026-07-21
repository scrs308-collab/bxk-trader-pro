import asyncio
from decimal import Decimal

from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Greeks, Quote

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

    except (TypeError, ValueError):
        return default


async def fetch_live_market_data(symbols: list[str]) -> dict:
    """
    Fetch quotes and Greeks for the requested option streamer symbols.
    """

    session = Session(
        TASTYTRADE_CLIENT_SECRET,
        TASTYTRADE_REFRESH_TOKEN,
    )

    market_data = {
        symbol: {
            "bid": 0.0,
            "ask": 0.0,
            "bid_size": 0.0,
            "ask_size": 0.0,
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "rho": None,
            "volatility": None,
        }
        for symbol in symbols
    }

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, symbols)
        await streamer.subscribe(Greeks, symbols)

        quote_symbols_received = set()
        greek_symbols_received = set()

        max_attempts = max(len(symbols) * 12, 20)
        attempts = 0

        while attempts < max_attempts:
            attempts += 1

            try:
                quote = await asyncio.wait_for(
                    streamer.get_event(Quote),
                    timeout=1.5,
                )

                symbol = getattr(
                    quote,
                    "event_symbol",
                    None,
                )

                if symbol in market_data:
                    market_data[symbol].update(
                        {
                            "bid": to_float(
                                getattr(
                                    quote,
                                    "bid_price",
                                    0,
                                )
                            ),
                            "ask": to_float(
                                getattr(
                                    quote,
                                    "ask_price",
                                    0,
                                )
                            ),
                            "bid_size": to_float(
                                getattr(
                                    quote,
                                    "bid_size",
                                    0,
                                )
                            ),
                            "ask_size": to_float(
                                getattr(
                                    quote,
                                    "ask_size",
                                    0,
                                )
                            ),
                        }
                    )

                    quote_symbols_received.add(
                        symbol
                    )

            except asyncio.TimeoutError:
                pass

            try:
                greek = await asyncio.wait_for(
                    streamer.get_event(Greeks),
                    timeout=1.5,
                )

                symbol = getattr(
                    greek,
                    "event_symbol",
                    None,
                )

                if symbol in market_data:
                    market_data[symbol].update(
                        {
                            "delta": to_float(
                                getattr(
                                    greek,
                                    "delta",
                                    None,
                                ),
                                None,
                            ),
                            "gamma": to_float(
                                getattr(
                                    greek,
                                    "gamma",
                                    None,
                                ),
                                None,
                            ),
                            "theta": to_float(
                                getattr(
                                    greek,
                                    "theta",
                                    None,
                                ),
                                None,
                            ),
                            "vega": to_float(
                                getattr(
                                    greek,
                                    "vega",
                                    None,
                                ),
                                None,
                            ),
                            "rho": to_float(
                                getattr(
                                    greek,
                                    "rho",
                                    None,
                                ),
                                None,
                            ),
                            "volatility": to_float(
                                getattr(
                                    greek,
                                    "volatility",
                                    None,
                                ),
                                None,
                            ),
                        }
                    )

                    greek_symbols_received.add(
                        symbol
                    )

            except asyncio.TimeoutError:
                pass

            if (
                len(quote_symbols_received) == len(symbols)
                and len(greek_symbols_received) == len(symbols)
            ):
                break

    return market_data


def get_live_market_data(symbols: list[str]) -> dict:
    try:
        return asyncio.run(
            fetch_live_market_data(symbols)
        )

    except RuntimeError:
        loop = asyncio.new_event_loop()

        try:
            return loop.run_until_complete(
                fetch_live_market_data(symbols)
            )
        finally:
            loop.close()

    except Exception as error:
        print(
            f"LIVE MARKET DATA ERROR: {error}"
        )
        return {}


def get_live_quotes(symbols: list[str]) -> dict:
    """
    Backward-compatible wrapper.
    """

    return get_live_market_data(symbols)


def mid_price(quote: dict) -> float:
    bid = to_float(quote.get("bid"))
    ask = to_float(quote.get("ask"))

    if bid > 0 and ask > 0:
        return round(
            (bid + ask) / 2,
            2,
        )

    return max(
        bid,
        ask,
        0,
    )


def calculate_probability_metrics(
    sell_put: dict,
    sell_call: dict,
) -> dict:
    """
    Estimate probability metrics from short-leg deltas.

    These are practical delta-based estimates, not guarantees.
    """

    put_delta = abs(
        to_float(
            sell_put.get("delta"),
            0,
        )
    )

    call_delta = abs(
        to_float(
            sell_call.get("delta"),
            0,
        )
    )

    if put_delta <= 0 or call_delta <= 0:
        return {
            "short_put_delta": None,
            "short_call_delta": None,
            "put_probability_otm": None,
            "call_probability_otm": None,
            "pop": None,
            "probability_of_touch": None,
        }

    put_probability_otm = round(
        (1 - put_delta) * 100,
        1,
    )

    call_probability_otm = round(
        (1 - call_delta) * 100,
        1,
    )

    pop = round(
        min(
            put_probability_otm,
            call_probability_otm,
        ),
        1,
    )

    probability_of_touch = round(
        max(
            put_delta,
            call_delta,
        )
        * 200,
        1,
    )

    probability_of_touch = min(
        probability_of_touch,
        100,
    )

    return {
        "short_put_delta": round(
            put_delta,
            4,
        ),
        "short_call_delta": round(
            call_delta,
            4,
        ),
        "put_probability_otm": (
            put_probability_otm
        ),
        "call_probability_otm": (
            call_probability_otm
        ),
        "pop": pop,
        "probability_of_touch": (
            probability_of_touch
        ),
    }


def calculate_iron_condor_credit(
    trade: dict,
) -> dict:
    symbols = [
        trade["sell_put_streamer"],
        trade["buy_put_streamer"],
        trade["sell_call_streamer"],
        trade["buy_call_streamer"],
    ]

    quotes = get_live_market_data(
        symbols
    )

    sell_put = quotes.get(
        trade["sell_put_streamer"],
        {},
    )

    buy_put = quotes.get(
        trade["buy_put_streamer"],
        {},
    )

    sell_call = quotes.get(
        trade["sell_call_streamer"],
        {},
    )

    buy_call = quotes.get(
        trade["buy_call_streamer"],
        {},
    )

    sell_put_mid = mid_price(sell_put)
    buy_put_mid = mid_price(buy_put)
    sell_call_mid = mid_price(sell_call)
    buy_call_mid = mid_price(buy_call)

    put_credit = (
        sell_put_mid
        - buy_put_mid
    )

    call_credit = (
        sell_call_mid
        - buy_call_mid
    )

    total_credit = round(
        put_credit + call_credit,
        2,
    )

    probability_metrics = (
        calculate_probability_metrics(
            sell_put=sell_put,
            sell_call=sell_call,
        )
    )

    return {
        "live_credit": round(
            max(total_credit, 0),
            2,
        ),
        "put_credit": round(
            put_credit,
            2,
        ),
        "call_credit": round(
            call_credit,
            2,
        ),
        "sell_put_mid": sell_put_mid,
        "buy_put_mid": buy_put_mid,
        "sell_call_mid": sell_call_mid,
        "buy_call_mid": buy_call_mid,

        "short_put_delta": (
            probability_metrics[
                "short_put_delta"
            ]
        ),
        "short_call_delta": (
            probability_metrics[
                "short_call_delta"
            ]
        ),
        "put_probability_otm": (
            probability_metrics[
                "put_probability_otm"
            ]
        ),
        "call_probability_otm": (
            probability_metrics[
                "call_probability_otm"
            ]
        ),
        "pop": probability_metrics[
            "pop"
        ],
        "probability_of_touch": (
            probability_metrics[
                "probability_of_touch"
            ]
        ),

        "quotes": quotes,
    }


def calculate_bull_put_credit(
    trade: dict,
) -> dict:
    symbols = [
        trade["sell_put_streamer"],
        trade["buy_put_streamer"],
    ]

    quotes = get_live_market_data(
        symbols
    )

    sell_put = quotes.get(
        trade["sell_put_streamer"],
        {},
    )

    buy_put = quotes.get(
        trade["buy_put_streamer"],
        {},
    )

    sell_put_mid = mid_price(
        sell_put
    )

    buy_put_mid = mid_price(
        buy_put
    )

    put_credit = round(
        sell_put_mid - buy_put_mid,
        2,
    )

    short_put_delta = abs(
        to_float(
            sell_put.get("delta"),
            0,
        )
    )

    if short_put_delta > 0:
        put_probability_otm = round(
            (1 - short_put_delta) * 100,
            1,
        )

        probability_of_touch = round(
            short_put_delta * 200,
            1,
        )

        probability_of_touch = min(
            probability_of_touch,
            100,
        )

        short_put_delta_value = round(
            short_put_delta,
            4,
        )

    else:
        put_probability_otm = None
        probability_of_touch = None
        short_put_delta_value = None

    return {
        "live_credit": round(
            max(
                put_credit,
                0,
            ),
            2,
        ),
        "put_credit": put_credit,
        "sell_put_mid": sell_put_mid,
        "buy_put_mid": buy_put_mid,
        "short_put_delta": (
            short_put_delta_value
        ),
        "put_probability_otm": (
            put_probability_otm
        ),
        "pop": put_probability_otm,
        "probability_of_touch": (
            probability_of_touch
        ),
        "quotes": quotes,
    }

def calculate_bear_call_credit(
    trade: dict,
) -> dict:
    """
    Calculate live pricing and probability metrics for a
    Bear Call Credit Spread.
    """

    symbols = [
        trade["sell_call_streamer"],
        trade["buy_call_streamer"],
    ]

    quotes = get_live_market_data(
        symbols
    )

    sell_call = quotes.get(
        trade["sell_call_streamer"],
        {},
    )

    buy_call = quotes.get(
        trade["buy_call_streamer"],
        {},
    )

    sell_call_mid = mid_price(
        sell_call
    )

    buy_call_mid = mid_price(
        buy_call
    )

    call_credit = round(
        sell_call_mid - buy_call_mid,
        2,
    )

    short_call_delta = abs(
        to_float(
            sell_call.get("delta"),
            0,
        )
    )

    if short_call_delta > 0:
        call_probability_otm = round(
            (1 - short_call_delta) * 100,
            1,
        )

        probability_of_touch = round(
            short_call_delta * 200,
            1,
        )

        probability_of_touch = min(
            probability_of_touch,
            100,
        )

        short_call_delta_value = round(
            short_call_delta,
            4,
        )

    else:
        call_probability_otm = None
        probability_of_touch = None
        short_call_delta_value = None

    return {
        "live_credit": round(
            max(
                call_credit,
                0,
            ),
            2,
        ),
        "call_credit": call_credit,
        "sell_call_mid": sell_call_mid,
        "buy_call_mid": buy_call_mid,
        "short_call_delta": (
            short_call_delta_value
        ),
        "call_probability_otm": (
            call_probability_otm
        ),
        "pop": call_probability_otm,
        "probability_of_touch": (
            probability_of_touch
        ),
        "quotes": quotes,
    }