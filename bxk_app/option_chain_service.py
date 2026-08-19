from datetime import date, datetime
from zoneinfo import ZoneInfo

from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.live_option_engine import (
    get_live_market_data,
    mid_price,
)


MARKET_TIMEZONE = ZoneInfo("America/New_York")


def normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise ValueError(
            "Underlying symbol must be a string."
        )

    normalized = (
        symbol.strip()
        .upper()
        .replace("$", "")
    )

    if not normalized:
        raise ValueError(
            "Underlying symbol cannot be empty."
        )

    return normalized


def calculate_actual_dte(
    expiration_value,
) -> int:
    """
    Calculate calendar DTE using the US market date.
    """

    if not expiration_value:
        return -1

    try:
        if isinstance(
            expiration_value,
            datetime,
        ):
            expiration_date = (
                expiration_value.date()
            )

        elif isinstance(
            expiration_value,
            date,
        ):
            expiration_date = expiration_value

        else:
            expiration_date = date.fromisoformat(
                str(expiration_value)[:10]
            )

    except (TypeError, ValueError):
        return -1

    market_today = datetime.now(
        MARKET_TIMEZONE
    ).date()

    return (
        expiration_date
        - market_today
    ).days


def get_nested_option_chain(
    symbol: str,
) -> dict | None:
    """
    Retrieve a Tastytrade nested option chain for any
    supported underlying.
    """

    normalized = normalize_symbol(symbol)

    getter = getattr(
        tastytrade_api,
        "get_nested_option_chain",
        None,
    )

    if getter is None:
        raise RuntimeError(
            "Tastytrade generic option-chain "
            "support is unavailable."
        )

    return getter(normalized)


def get_strikes_by_dte(
    symbol: str,
    days_to_expiration: int = 0,
) -> list[dict]:
    """
    Return strikes for the exact requested calendar DTE.

    Never silently substitute another expiration.
    """

    normalized = normalize_symbol(symbol)

    chain = get_nested_option_chain(
        normalized
    )

    if not chain:
        return []

    items = chain.get("items", [])

    if not items:
        return []

    expirations = items[0].get(
        "expirations",
        [],
    )

    selected = None

    for expiration in expirations:
        expiration_date = expiration.get(
            "expiration-date"
        )

        actual_dte = calculate_actual_dte(
            expiration_date
        )

        if actual_dte == days_to_expiration:
            selected = {
                "dte": actual_dte,
                "data": expiration,
            }
            break

    if selected is None:
        return []

    selected_expiration = selected["data"]

    strikes = []

    for strike in selected_expiration.get(
        "strikes",
        [],
    ):
        try:
            strike_price = float(
                strike.get("strike-price")
            )
        except (TypeError, ValueError):
            continue

        if strike_price <= 0:
            continue

        strikes.append(
            {
                "underlying": normalized,
                "strike": strike_price,
                "call": strike.get("call"),
                "put": strike.get("put"),
                "call_streamer": strike.get(
                    "call-streamer-symbol"
                ),
                "put_streamer": strike.get(
                    "put-streamer-symbol"
                ),
                "expiration_date": (
                    selected_expiration.get(
                        "expiration-date"
                    )
                ),
                "days_to_expiration": (
                    selected["dte"]
                ),
                "settlement_type": (
                    selected_expiration.get(
                        "settlement-type"
                    )
                ),
            }
        )

    return sorted(
        strikes,
        key=lambda item: item["strike"],
    )


def find_nearest_strike(
    target_price: float,
    strikes: list[dict],
) -> dict | None:
    if not strikes:
        return None

    return min(
        strikes,
        key=lambda item: abs(
            item["strike"] - target_price
        ),
    )


def unavailable_expected_move(
    *,
    symbol: str,
    reason_code: str,
    days_to_expiration: int,
) -> dict:
    return {
        "available": False,
        "signal_ready": False,
        "underlying": symbol,
        "expected_move": None,
        "expected_move_pct": None,
        "atm_strike": None,
        "call_mid": None,
        "put_mid": None,
        "expiration": None,
        "dte": days_to_expiration,
        "source": (
            "OPTION_CHAIN_ATM_STRADDLE"
        ),
        "reason_code": reason_code,
    }


def calculate_atm_straddle_expected_move(
    symbol: str,
    underlying_price: float,
    days_to_expiration: int = 0,
) -> dict:
    """
    Estimate the option-implied move from the ATM
    call + ATM put midpoint for the requested expiration.

    This produces an underlying-specific option-chain
    move and does not borrow SPX/VIX expected-move data.
    """

    normalized = normalize_symbol(symbol)

    try:
        spot = float(underlying_price)
    except (TypeError, ValueError):
        spot = 0.0

    if spot <= 0:
        return unavailable_expected_move(
            symbol=normalized,
            reason_code=(
                "UNDERLYING_PRICE_UNAVAILABLE"
            ),
            days_to_expiration=(
                days_to_expiration
            ),
        )

    strikes = get_strikes_by_dte(
        normalized,
        days_to_expiration,
    )

    if not strikes:
        return unavailable_expected_move(
            symbol=normalized,
            reason_code=(
                "OPTION_CHAIN_UNAVAILABLE"
            ),
            days_to_expiration=(
                days_to_expiration
            ),
        )

    atm = find_nearest_strike(
        spot,
        strikes,
    )

    if not atm:
        return unavailable_expected_move(
            symbol=normalized,
            reason_code="ATM_STRIKE_UNAVAILABLE",
            days_to_expiration=(
                days_to_expiration
            ),
        )

    call_streamer = atm.get(
        "call_streamer"
    )

    put_streamer = atm.get(
        "put_streamer"
    )

    if not call_streamer or not put_streamer:
        result = unavailable_expected_move(
            symbol=normalized,
            reason_code=(
                "STREAMER_SYMBOL_UNAVAILABLE"
            ),
            days_to_expiration=(
                days_to_expiration
            ),
        )

        result["atm_strike"] = atm["strike"]
        result["expiration"] = atm.get(
            "expiration_date"
        )

        return result

    quotes = get_live_market_data(
        [
            call_streamer,
            put_streamer,
        ]
    )

    call_quote = quotes.get(
        call_streamer,
        {},
    )

    put_quote = quotes.get(
        put_streamer,
        {},
    )

    call_mid = mid_price(call_quote)
    put_mid = mid_price(put_quote)

    if call_mid <= 0 or put_mid <= 0:
        result = unavailable_expected_move(
            symbol=normalized,
            reason_code=(
                "LIVE_OPTION_DATA_UNAVAILABLE"
            ),
            days_to_expiration=(
                days_to_expiration
            ),
        )

        result["atm_strike"] = atm["strike"]
        result["expiration"] = atm.get(
            "expiration_date"
        )
        result["call_mid"] = call_mid
        result["put_mid"] = put_mid

        return result

    expected_move = round(
        call_mid + put_mid,
        2,
    )

    expected_move_pct = round(
        expected_move / spot * 100,
        2,
    )

    return {
        "available": True,
        "signal_ready": True,
        "underlying": normalized,
        "expected_move": expected_move,
        "expected_move_pct": (
            expected_move_pct
        ),
        "atm_strike": atm["strike"],
        "call_mid": call_mid,
        "put_mid": put_mid,
        "expiration": atm.get(
            "expiration_date"
        ),
        "dte": int(
            atm.get(
                "days_to_expiration",
                days_to_expiration,
            )
        ),
        "source": (
            "OPTION_CHAIN_ATM_STRADDLE"
        ),
        "reason_code": (
            "OPTION_CHAIN_EXPECTED_MOVE_READY"
        ),
    }
