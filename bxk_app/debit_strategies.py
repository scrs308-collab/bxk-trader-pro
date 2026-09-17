"""Manual defined-risk debit structures, shared by pricing and execution."""
import math
from datetime import datetime, timezone

DEBIT_NAMES = {
    "reverse_iron_condor": "Reverse Iron Condor",
    "butterfly": "Butterfly",
    "debit_call_spread": "Debit Call Spread",
    "debit_put_spread": "Debit Put Spread",
}
STRATEGY_PATTERN = "^(auto|iron_condor|reverse_iron_condor|butterfly|bull_put_credit_spread|bear_call_credit_spread|debit_call_spread|debit_put_spread)$"
PATTERNS = {
    "reverse_iron_condor": [("SELL", "PUT", 1), ("BUY", "PUT", 1), ("BUY", "CALL", 1), ("SELL", "CALL", 1)],
    "butterfly": [("BUY", "CALL", 1), ("SELL", "CALL", 2), ("BUY", "CALL", 1)],
    "debit_call_spread": [("BUY", "CALL", 1), ("SELL", "CALL", 1)],
    "debit_put_spread": [("BUY", "PUT", 1), ("SELL", "PUT", 1)],
}


def strategy_key(value):
    return str(value or "").strip().lower().removeprefix("spx ").replace(" ", "_").replace("-", "_")


def debit_risk(strategy, legs, debit):
    key = strategy_key(strategy)
    pattern = PATTERNS[key]
    if len(legs) != len(pattern) or any(
        (leg.get("action"), leg.get("option_type"), leg.get("quantity", 1)) != expected
        for leg, expected in zip(legs, pattern)
    ):
        raise ValueError("Invalid debit leg actions, types, or ratios.")
    strikes = [float(leg["strike"]) for leg in legs]
    if not all(math.isfinite(s) and s > 0 for s in strikes):
        raise ValueError("Invalid strikes.")
    ordered = strikes[::-1] if key == "debit_put_spread" else strikes
    if any(a >= b for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Strategy strikes are not ordered correctly.")
    width = abs(strikes[1] - strikes[0])
    if key in {"reverse_iron_condor", "butterfly"} and not math.isclose(width, strikes[-1] - strikes[-2], abs_tol=1e-8):
        raise ValueError("Spread/wing widths must match.")
    debit = float(debit)
    if not math.isfinite(debit) or not 0 < debit < width:
        raise ValueError("Net debit must be greater than zero and less than width.")
    if key == "reverse_iron_condor":
        breakevens = [strikes[1] - debit, strikes[2] + debit]
    elif key == "butterfly":
        breakevens = [strikes[0] + debit, strikes[2] - debit]
    else:
        breakevens = [strikes[0] + (debit if key == "debit_call_spread" else -debit)]
    return {
        "width": width, "wing_width": width, "debit": debit,
        "max_loss": round(debit * 100, 2), "max_risk": round(debit * 100, 2),
        "max_profit": round((width - debit) * 100, 2),
        "breakevens": [round(b, 2) for b in breakevens],
        "risk_classification": "Defined risk · " + ("long volatility" if key == "reverse_iron_condor" else "pinning" if key == "butterfly" else "directional"),
        "price_effect": "Debit",
    }


def quote_epoch_seconds(timestamp):
    if timestamp is None:
        raise ValueError("Quote timestamp is missing.")

    if isinstance(timestamp, (int, float)):
        stamp = float(timestamp)
        if stamp > 1e11:
            stamp /= 1000
    else:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Quote timestamp must include timezone.")
        stamp = parsed.timestamp()

    if not math.isfinite(stamp) or stamp <= 0:
        raise ValueError("Quote timestamp is invalid.")

    return stamp


def quote_age(timestamp, now=None):
    stamp = quote_epoch_seconds(
        timestamp
    )

    age = (now or datetime.now(timezone.utc).timestamp()) - stamp
    if not math.isfinite(age) or age < -5 or age > 60:
        raise ValueError("Option quote is stale or has an invalid timestamp.")
    return max(0, age)


def price_debit_legs(strategy, legs, quotes):
    debit = 0
    ages = []
    bid_value = ask_value = 0
    for leg in legs:
        quote = quotes.get(leg.get("streamer_symbol")) or {}
        try:
            bid, ask = float(quote["bid"]), float(quote["ask"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Option quotes are incomplete.") from exc
        if not math.isfinite(bid + ask) or bid < 0 or ask <= 0 or ask < bid:
            raise ValueError("Option quotes are incomplete or crossed.")
        timestamp = quote.get("quote_timestamp")
        ages.append(quote_age(timestamp))
        ratio = leg["quantity"] * (1 if leg["action"] == "BUY" else -1)
        debit += ratio * (bid + ask) / 2
        bid_value += ratio * (bid if ratio > 0 else ask)
        ask_value += ratio * (ask if ratio > 0 else bid)
    debit = round(debit, 4)
    oldest = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - max(ages), timezone.utc).isoformat()
    return {**debit_risk(strategy, legs, debit), "midpoint": debit,
            "combo_bid": round(bid_value, 4), "combo_ask": round(ask_value, 4),
            "quote_timestamp": oldest, "quote_age_seconds": round(max(ages), 2)}


def construct_legs(strategy, chain, spot, width, expected_move):
    key = strategy_key(strategy)
    rows = {float(row["strike"]): row for row in chain}
    if not rows or width <= 0:
        raise ValueError("No listed strikes for the selected expiration/width.")
    candidates = []
    for center in sorted(rows, key=lambda s: (abs(s - spot), s)):
        strikes = ([center - width, center, center + width] if key == "butterfly" else
                   [center, center + width] if key == "debit_call_spread" else
                   [center, center - width] if key == "debit_put_spread" else [])
        if strikes and all(s in rows for s in strikes):
            candidates.append(strikes)
    if key == "reverse_iron_condor":
        puts = sorted((s for s in rows if s < spot and s - width in rows), key=lambda s: abs(s - (spot - expected_move / 2)))
        calls = sorted((s for s in rows if s > spot and s + width in rows), key=lambda s: abs(s - (spot + expected_move / 2)))
        if puts and calls:
            candidates = [[puts[0] - width, puts[0], calls[0], calls[0] + width]]
    for strikes in candidates:
        legs = []
        for strike, (action, kind, ratio) in zip(strikes, PATTERNS[key]):
            row = rows[strike]
            legs.append({"action": action, "option_type": kind, "quantity": ratio,
                         "strike": strike, "symbol": row.get(kind.lower()),
                         "streamer_symbol": row.get(kind.lower() + "_streamer")})
        if all(leg["symbol"] and leg["streamer_symbol"] for leg in legs):
            return legs
    raise ValueError("A valid structure cannot be built from available strikes and symbols.")


def build_manual_debit(strategy, dte, wing_width):
    from bxk_app.trade_builder import refresh_live_trade_context
    from bxk_app.option_scanner import get_spx_strikes_by_dte
    from bxk_app.live_option_engine import get_live_market_data
    market, snapshot, error = refresh_live_trade_context()
    if error:
        return error
    try:
        chain = get_spx_strikes_by_dte(dte)
        spot = float(snapshot.get("spx") or snapshot.get("price"))
        legs = construct_legs(strategy, chain, spot, wing_width, float(snapshot["expected_move"]))
        pricing = price_debit_legs(strategy, legs, get_live_market_data([leg["streamer_symbol"] for leg in legs]))
        trade = {"strategy": DEBIT_NAMES[strategy], "symbol": "SPX", "spx_price": spot,
                 "manual_selection": True, "structure_validated": True,
                 "expiration": chain[0]["expiration_date"], "dte": dte, "legs": legs,
                 "expected_move": snapshot["expected_move"], **pricing}
        trade["buying_power"] = trade["max_risk"]
        return {"status": "READY", "best_trade": trade}
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "NO TRADE", "best_trade": None, "reason_code": "INVALID_DEBIT_STRUCTURE", "message": str(exc)}
    except (RuntimeError, OSError):
        return {"status": "NO TRADE", "best_trade": None, "reason_code": "LIVE_QUOTES_UNAVAILABLE", "message": "Live option chain or quotes are unavailable. Try a fresh preview."}


def credit_preview_metadata(trade):
    """Enrich existing credit previews without changing selection or eligibility."""
    key = strategy_key(trade.get("strategy"))
    fields = (["sell_put", "buy_put", "sell_call", "buy_call"] if key == "iron_condor" else
              ["sell_put", "buy_put"] if "put" in key else ["sell_call", "buy_call"])
    legs = [{"action": "SELL" if field.startswith("sell") else "BUY", "quantity": 1,
             "option_type": "PUT" if field.endswith("put") else "CALL",
             "strike": trade.get(field), "symbol": trade.get(field + "_symbol")}
            for field in fields]
    credit = float(trade.get("credit") or 0)
    breakevens = []
    if trade.get("sell_put") is not None:
        breakevens.append(round(trade["sell_put"] - credit, 2))
    if trade.get("sell_call") is not None:
        breakevens.append(round(trade["sell_call"] + credit, 2))
    quotes = (
        trade.get(
            "credit_details",
            {},
        ).get("quotes")
        or {}
    )

    quote_keys = [
        trade.get(
            f"{field}_streamer"
        )
        for field in fields
    ]

    selected_quotes = [
        (
            quotes.get(
                quote_key,
                {},
            )
            if quote_key
            else {}
        )
        for quote_key in quote_keys
    ]

    stamps = [
        (
            quote.get(
                "quote_timestamp"
            )
        )
        for quote in selected_quotes
    ]

    quotes_are_complete = True

    for quote in selected_quotes:
        try:
            bid = float(quote["bid"])
            ask = float(quote["ask"])
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            quotes_are_complete = False
            break

        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid < 0
            or ask <= 0
            or ask < bid
        ):
            quotes_are_complete = False
            break

    quote_timestamp = None
    age = None

    quote_is_fresh = False

    if (
        all(quote_keys)
        and all(stamps)
        and quotes_are_complete
    ):
        try:
            numeric = [
                quote_epoch_seconds(stamp)
                for stamp in stamps
            ]

            oldest = min(numeric)

            quote_timestamp = (
                datetime.fromtimestamp(
                    oldest,
                    timezone.utc,
                ).isoformat()
            )

            age = max(
                0,
                datetime.now(
                    timezone.utc
                ).timestamp()
                - oldest,
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
            OSError,
        ):
            quote_timestamp = None
            age = None
            quote_is_fresh = False

        else:
            try:
                quote_is_fresh = all(
                    quote_age(stamp) <= 60
                    for stamp in stamps
                )
            except (
                TypeError,
                ValueError,
            ):
                quote_is_fresh = False

    execution_reason = (
        "Option quotes are fresh."
        if quote_is_fresh
        else (
            "Option quote timestamps are missing "
            "or stale. Refresh the trade before execution."
        )
    )

    trade.update(legs=legs, price_effect="Credit", midpoint=credit, breakevens=breakevens,
                 width=trade.get("wing_width"), max_loss=trade.get("max_risk"),
                 risk_classification="Defined risk · credit", quote_timestamp=quote_timestamp,
                 quote_age_seconds=round(age, 2) if age is not None else None,
                 quote_is_fresh=quote_is_fresh,
                 execution={"status": "READY" if quote_is_fresh else "BLOCKED",
                            "ready": quote_is_fresh, "reason": execution_reason})
