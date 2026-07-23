from fastapi import APIRouter

from bxk_app.broker_tastytrade import tastytrade_api


router = APIRouter(
    prefix="/api",
    tags=["Options"],
)


@router.get("/test-spx-option-quotes")
def test_spx_option_quotes():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {
            "error": "No chain",
        }

    item = chain["items"][0]
    expiration = item["expirations"][0]
    strikes = expiration["strikes"]

    sample_symbols = []

    for strike in strikes:
        price = float(
            strike["strike-price"]
        )

        if 7450 <= price <= 7625:
            sample_symbols.append(
                strike["put-streamer-symbol"]
            )
            sample_symbols.append(
                strike["call-streamer-symbol"]
            )

        if len(sample_symbols) >= 10:
            break

    quotes = tastytrade_api.get_option_quotes(
        sample_symbols
    )

    return {
        "using": "streamer-symbols",
        "sample_symbols": sample_symbols,
        "quote_count": len(quotes),
        "quotes": quotes,
        "status": tastytrade_api.get_status(),
    }


@router.get("/test-expirations")
def test_expirations():
    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return {
            "error": "No chain",
        }

    item = chain["items"][0]

    return {
        "expirations": [
            {
                "date": expiration.get(
                    "expiration-date"
                ),
                "dte": expiration.get(
                    "days-to-expiration"
                ),
                "type": expiration.get(
                    "expiration-type"
                ),
                "settlement": expiration.get(
                    "settlement-type"
                ),
                "strike_count": len(
                    expiration.get(
                        "strikes",
                        [],
                    )
                ),
            }
            for expiration in item.get(
                "expirations",
                [],
            )[:10]
        ]
    }


@router.get("/test-option-quote-fields")
def test_option_quote_fields():
    from bxk_app.trade_builder import build_best_trade

    result = build_best_trade(
        wing_width=25,
        days_to_expiration=1,
        min_credit=1.00,
    )

    trade = result.get(
        "best_trade"
    )

    if not trade:
        return {
            "error": "No best trade returned",
            "result": result,
        }

    symbols = [
        trade.get("sell_put_symbol"),
        trade.get("buy_put_symbol"),
        trade.get("sell_call_symbol"),
        trade.get("buy_call_symbol"),
    ]

    symbols = [
        symbol
        for symbol in symbols
        if symbol
    ]

    quotes = tastytrade_api.get_option_quotes(
        symbols
    )

    return {
        "symbols_sent": symbols,
        "quote_count": len(quotes),
        "first_quote_keys": (
            list(quotes[0].keys())
            if quotes
            else []
        ),
        "quotes": quotes,
        "status": tastytrade_api.get_status(),
    }