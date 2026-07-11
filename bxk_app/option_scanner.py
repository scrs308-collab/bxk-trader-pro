from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.scanner_settings import scanner_settings
from bxk_app.trade_quality import score_candidate
from bxk_app.live_option_engine import calculate_iron_condor_credit


def safe_float(value, default: float = 0.0) -> float:
    """
    Safely convert a value to float.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_spx_strikes_by_dte(days_to_expiration: int = 0):
    """
    Return SPX strikes for the requested DTE.

    Selection order:
    1. Exact requested DTE
    2. Nearest later expiration
    3. Nearest available expiration

    This handles weekends and market holidays when an exact
    calendar-day DTE may not exist.
    """

    chain = tastytrade_api.get_spx_option_chain()

    if not chain:
        return []

    items = chain.get("items", [])

    if not items:
        return []

    expirations = items[0].get("expirations", [])

    valid_expirations = []

    for expiration in expirations:
        try:
            dte = int(
                expiration.get(
                    "days-to-expiration",
                    -1,
                )
            )
        except (TypeError, ValueError):
            continue

        if dte < 0:
            continue

        valid_expirations.append(
            {
                "dte": dte,
                "data": expiration,
            }
        )

    if not valid_expirations:
        return []

    # First preference: exact requested DTE
    selected = next(
        (
            item
            for item in valid_expirations
            if item["dte"] == days_to_expiration
        ),
        None,
    )

    # Second preference: nearest later expiration
    if selected is None:
        later_expirations = [
            item
            for item in valid_expirations
            if item["dte"] > days_to_expiration
        ]

        if later_expirations:
            selected = min(
                later_expirations,
                key=lambda item: item["dte"],
            )

    # Final fallback: nearest available expiration
    if selected is None:
        selected = min(
            valid_expirations,
            key=lambda item: abs(
                item["dte"] - days_to_expiration
            ),
        )

    selected_expiration = selected["data"]

    strikes = []

    for strike in selected_expiration.get("strikes", []):
        strike_price = safe_float(
            strike.get("strike-price")
        )

        if strike_price <= 0:
            continue

        strikes.append(
            {
                "strike": strike_price,
                "call": strike.get("call"),
                "put": strike.get("put"),
                "call_streamer": strike.get(
                    "call-streamer-symbol"
                ),
                "put_streamer": strike.get(
                    "put-streamer-symbol"
                ),
                "expiration_date": selected_expiration.get(
                    "expiration-date"
                ),
                "days_to_expiration": selected_expiration.get(
                    "days-to-expiration"
                ),
                "settlement_type": selected_expiration.get(
                    "settlement-type"
                ),
            }
        )

    return sorted(
        strikes,
        key=lambda item: item["strike"],
    )


def get_0dte_spx_strikes():
    """
    Return the current 0DTE SPX strike list.
    """

    return get_spx_strikes_by_dte(0)


def find_nearest_strike(
    target_price: float,
    strikes: list[dict],
):
    """
    Find the option-chain strike nearest to the target price.
    """

    if not strikes:
        return None

    return min(
        strikes,
        key=lambda item: abs(
            item["strike"] - target_price
        ),
    )


def build_chain_based_iron_condor(
    spx_price: float,
    expected_move: float,
    wing_width: int | None = None,
):
    """
    Build one 0DTE iron condor centered around the expected move.
    """

    if wing_width is None:
        wing_width = scanner_settings.wing_width

    strikes = get_0dte_spx_strikes()

    if not strikes:
        return None

    short_put_target = spx_price - expected_move
    short_call_target = spx_price + expected_move

    short_put = find_nearest_strike(
        short_put_target,
        strikes,
    )

    short_call = find_nearest_strike(
        short_call_target,
        strikes,
    )

    if not short_put or not short_call:
        return None

    long_put_target = (
        short_put["strike"] - wing_width
    )

    long_call_target = (
        short_call["strike"] + wing_width
    )

    long_put = find_nearest_strike(
        long_put_target,
        strikes,
    )

    long_call = find_nearest_strike(
        long_call_target,
        strikes,
    )

    if not long_put or not long_call:
        return None

    return {
        "strategy": "IRON CONDOR",
        "source": "LIVE_CHAIN",
        "expiration": short_put.get(
            "expiration_date"
        ),
        "dte": int(
            short_put.get(
                "days_to_expiration",
                0,
            )
        ),
        "settlement_type": short_put.get(
            "settlement_type"
        ),
        "spx_price": round(spx_price, 2),
        "expected_move": round(
            expected_move,
            2,
        ),

        "sell_put": int(
            short_put["strike"]
        ),
        "buy_put": int(
            long_put["strike"]
        ),
        "sell_call": int(
            short_call["strike"]
        ),
        "buy_call": int(
            long_call["strike"]
        ),

        "sell_put_symbol": short_put["put"],
        "buy_put_symbol": long_put["put"],
        "sell_call_symbol": short_call["call"],
        "buy_call_symbol": long_call["call"],

        "sell_put_streamer": short_put[
            "put_streamer"
        ],
        "buy_put_streamer": long_put[
            "put_streamer"
        ],
        "sell_call_streamer": short_call[
            "call_streamer"
        ],
        "buy_call_streamer": long_call[
            "call_streamer"
        ],

        "put_buffer": round(
            spx_price - short_put["strike"],
            2,
        ),
        "call_buffer": round(
            short_call["strike"] - spx_price,
            2,
        ),
        "wing_width": int(
            short_put["strike"]
            - long_put["strike"]
        ),
    }


def generate_candidate_condors(
    spx_price: float,
    expected_move: float,
    wing_width: int | None = None,
    days_to_expiration: int = 0,
):
    """
    Generate a grid of potential SPX iron condors.
    """

    if wing_width is None:
        wing_width = scanner_settings.wing_width

    strikes = get_spx_strikes_by_dte(
        days_to_expiration
    )

    if not strikes:
        return []

    candidates = []
    seen = set()

    target_put = spx_price - expected_move
    target_call = spx_price + expected_move

    search_points = scanner_settings.search_points
    strike_increment = (
        scanner_settings.strike_increment
    )

    offsets = range(
        -search_points,
        search_points + strike_increment,
        strike_increment,
    )

    for offset in offsets:
        put_target = target_put + offset
        call_target = target_call - offset

        short_put = find_nearest_strike(
            put_target,
            strikes,
        )

        short_call = find_nearest_strike(
            call_target,
            strikes,
        )

        if not short_put or not short_call:
            continue

        long_put = find_nearest_strike(
            short_put["strike"] - wing_width,
            strikes,
        )

        long_call = find_nearest_strike(
            short_call["strike"] + wing_width,
            strikes,
        )

        if not long_put or not long_call:
            continue

        key = (
            short_put["strike"],
            long_put["strike"],
            short_call["strike"],
            long_call["strike"],
        )

        if key in seen:
            continue

        seen.add(key)

        candidates.append(
            {
                "sell_put": short_put,
                "buy_put": long_put,
                "sell_call": short_call,
                "buy_call": long_call,
            }
        )

        if (
            len(candidates)
            >= scanner_settings.max_candidates
        ):
            break

    return candidates


def find_best_candidate(
    candidates: list,
):
    """
    Price and rank a pre-generated list of candidates.
    """

    ranked = []

    for candidate in candidates:
        live = calculate_iron_condor_credit(
            candidate
        )

        credit = safe_float(
            live.get("live_credit", 0)
        )

        candidate["credit"] = credit
        candidate["put_credit"] = safe_float(
            live.get("put_credit", 0)
        )
        candidate["call_credit"] = safe_float(
            live.get("call_credit", 0)
        )

        # Temporary until live delta-based POP is added.
        candidate["pop"] = 85

        candidate["wing_width"] = int(
            candidate["sell_put"]["strike"]
            - candidate["buy_put"]["strike"]
        )

        candidate["put_buffer"] = safe_float(
            candidate.get("spx_price", 0)
        ) - candidate["sell_put"]["strike"]

        candidate["call_buffer"] = (
            candidate["sell_call"]["strike"]
            - safe_float(
                candidate.get("spx_price", 0)
            )
        )

        candidate["score"] = score_candidate(
            candidate
        )

        ranked.append(candidate)

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["credit"],
        ),
        reverse=True,
    )

    if ranked:
        return ranked[0]

    return None


def normalize_candidate(
    candidate: dict,
    spx_price: float,
    expected_move: float,
):
    """
    Flatten a raw chain-based candidate into the trade format
    used by the pricing and analysis engines.
    """

    sell_put = candidate["sell_put"]
    buy_put = candidate["buy_put"]
    sell_call = candidate["sell_call"]
    buy_call = candidate["buy_call"]

    return {
        "strategy": "IRON CONDOR",
        "source": "LIVE_CHAIN_RANKED",
        "expiration": sell_put.get(
            "expiration_date"
        ),
        "dte": int(
            sell_put.get(
                "days_to_expiration",
                0,
            )
        ),
        "settlement_type": sell_put.get(
            "settlement_type"
        ),
        "spx_price": round(spx_price, 2),
        "expected_move": round(
            expected_move,
            2,
        ),

        "sell_put": int(
            sell_put["strike"]
        ),
        "buy_put": int(
            buy_put["strike"]
        ),
        "sell_call": int(
            sell_call["strike"]
        ),
        "buy_call": int(
            buy_call["strike"]
        ),

        "sell_put_symbol": sell_put["put"],
        "buy_put_symbol": buy_put["put"],
        "sell_call_symbol": sell_call["call"],
        "buy_call_symbol": buy_call["call"],

        "sell_put_streamer": sell_put[
            "put_streamer"
        ],
        "buy_put_streamer": buy_put[
            "put_streamer"
        ],
        "sell_call_streamer": sell_call[
            "call_streamer"
        ],
        "buy_call_streamer": buy_call[
            "call_streamer"
        ],

        "put_buffer": round(
            spx_price - sell_put["strike"],
            2,
        ),
        "call_buffer": round(
            sell_call["strike"] - spx_price,
            2,
        ),
        "wing_width": int(
            sell_put["strike"]
            - buy_put["strike"]
        ),
    }


def find_best_ranked_iron_condor(
    spx_price: float,
    expected_move: float,
    wing_width: int | None = None,
    days_to_expiration: int = 0,
):
    """
    Generate, price, score, and rank SPX iron condors.
    """

    candidates = generate_candidate_condors(
        spx_price=spx_price,
        expected_move=expected_move,
        wing_width=wing_width,
        days_to_expiration=days_to_expiration,
    )

    if not candidates:
        return None

    ranked = []

    for raw_candidate in candidates:
        trade = normalize_candidate(
            raw_candidate,
            spx_price=spx_price,
            expected_move=expected_move,
        )

        live = calculate_iron_condor_credit(
            trade
        )

        credit = safe_float(
            live.get("live_credit", 0)
        )

        trade["credit"] = credit
        trade["live_credit"] = credit
        trade["target_credit"] = credit

        trade["put_credit"] = safe_float(
            live.get("put_credit", 0)
        )

        trade["call_credit"] = safe_float(
            live.get("call_credit", 0)
        )

        trade["max_risk"] = round(
            (
                trade["wing_width"]
                - credit
            )
            * 100,
            2,
        )

        trade["expected_profit"] = round(
            credit * 100,
            2,
        )

        if (
            credit > 0
            and trade["wing_width"] > credit
        ):
            trade["return_on_risk"] = round(
                (
                    credit
                    / (
                        trade["wing_width"]
                        - credit
                    )
                )
                * 100,
                2,
            )
        else:
            trade["return_on_risk"] = 0

        # Temporary until live delta-based POP is added.
        trade["pop"] = 85

        trade["score"] = score_candidate(
            trade
        )

        trade["trade_score"] = trade["score"]

        ranked.append(trade)

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["credit"],
            item["return_on_risk"],
        ),
        reverse=True,
    )

    best = ranked[0]

    best["candidates_evaluated"] = len(
        ranked
    )

    return best