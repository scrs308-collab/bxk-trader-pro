def _positive_float(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _select_future_price(quote):
    """
    Prefer the bid/ask midpoint for a live futures reference.

    Fall back to mark, last, then last-mkt when necessary.
    """

    if not isinstance(quote, dict):
        return None, "NONE"

    bid = _positive_float(
        quote.get("bid")
    )

    ask = _positive_float(
        quote.get("ask")
    )

    if bid is not None and ask is not None:
        if ask >= bid:
            return (
                (bid + ask) / 2.0,
                "MID",
            )

    for key, label in (
        ("mark", "MARK"),
        ("last", "LAST"),
        ("last-mkt", "LAST_MKT"),
    ):
        value = _positive_float(
            quote.get(key)
        )

        if value is not None:
            return value, label

    return None, "NONE"


def select_future_reference_price(
    quote,
):
    """
    Return the preferred futures reference price
    and its source label.
    """

    return _select_future_price(
        quote
    )


def calculate_overnight_spx_reference(
    *,
    prior_spx_close,
    es_quote,
    es_anchor_price=None,
):
    """
    Estimate the current overnight SPX level from ES movement.

    This is observation-only.

    Preferred future architecture:
        estimated SPX =
            prior SPX close
            + (
                current ES
                - ES price captured alongside SPX close
            )

    Until an exact closing ES anchor is persisted, the ES quote's
    prev-close may be used as a fallback anchor.
    """

    spx_close = _positive_float(
        prior_spx_close
    )

    if not isinstance(es_quote, dict):
        es_quote = {}

    es_price, price_source = (
        _select_future_price(
            es_quote
        )
    )

    supplied_anchor = _positive_float(
        es_anchor_price
    )

    if supplied_anchor is not None:
        anchor = supplied_anchor
        anchor_source = "CLOSE_SNAPSHOT"
        calibration_quality = "PREFERRED"

    else:
        anchor = _positive_float(
            es_quote.get(
                "prev-close"
            )
        )

        anchor_source = "ES_PREV_CLOSE"
        calibration_quality = "FALLBACK"

    symbol = (
        es_quote.get("symbol")
        or None
    )

    updated_at = (
        es_quote.get("updated-at")
        or None
    )

    if (
        spx_close is None
        or es_price is None
        or anchor is None
    ):
        return {
            "available": False,
            "observation_only": True,
            "state": "UNAVAILABLE",
            "reason_code":
                "OVERNIGHT_REFERENCE_DATA_UNAVAILABLE",
            "reference_source": "ES_PROXY",
            "symbol": symbol,
            "updated_at": updated_at,
        }

    es_move = es_price - anchor

    estimated_spx = (
        spx_close + es_move
    )

    reason_code = (
        "ES_CLOSE_ANCHOR_PROXY_AVAILABLE"
        if anchor_source == "CLOSE_SNAPSHOT"
        else "ES_PREV_CLOSE_PROXY_AVAILABLE"
    )

    return {
        "available": True,
        "observation_only": True,
        "state": "AVAILABLE",
        "reason_code": reason_code,

        "reference_source": "ES_PROXY",
        "calibration_quality":
            calibration_quality,

        "symbol": symbol,
        "price_source": price_source,

        "es_price": round(
            es_price,
            3,
        ),

        "es_anchor_price": round(
            anchor,
            3,
        ),

        "es_anchor_source":
            anchor_source,

        "es_move": round(
            es_move,
            3,
        ),

        "prior_spx_close": round(
            spx_close,
            2,
        ),

        "estimated_spx": round(
            estimated_spx,
            2,
        ),

        "updated_at": updated_at,
    }

from datetime import datetime, timezone


def _utc_datetime(value):
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value or "").strip()

        if not text:
            return None

        try:
            result = datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )
        except (TypeError, ValueError):
            return None

    # A risk-control timestamp without an explicit
    # timezone is ambiguous. Fail closed rather than
    # silently assuming UTC.
    if result.tzinfo is None:
        return None

    return result.astimezone(
        timezone.utc
    )


def evaluate_future_quote_health(
    *,
    quote,
    as_of=None,
    max_age_seconds=120,
    future_tolerance_seconds=5,
):
    """
    Fail-closed health evaluation for a live
    futures quote.

    This function is observation only.
    """

    if not isinstance(quote, dict):
        return {
            "available": False,
            "healthy": False,
            "reason_code":
                "ES_QUOTE_UNAVAILABLE",
        }

    halted = quote.get(
        "is-trading-halted"
    )

    halted_text = str(
        halted
    ).strip().lower()

    if (
        halted is True
        or halted_text
        in {"true", "1", "yes"}
    ):
        return {
            "available": False,
            "healthy": False,
            "reason_code":
                "ES_QUOTE_HALTED",
        }

    updated_at = _utc_datetime(
        quote.get("updated-at")
    )

    if updated_at is None:
        return {
            "available": False,
            "healthy": False,
            "reason_code":
                "ES_QUOTE_TIMESTAMP_UNAVAILABLE",
        }

    if as_of is None:
        current = datetime.now(
            timezone.utc
        )
    else:
        current = _utc_datetime(
            as_of
        )

        if current is None:
            return {
                "available": False,
                "healthy": False,
                "reason_code":
                    "ES_QUOTE_AS_OF_INVALID",
            }

    age_seconds = (
        current - updated_at
    ).total_seconds()

    if (
        age_seconds
        < -float(
            future_tolerance_seconds
        )
    ):
        return {
            "available": False,
            "healthy": False,
            "reason_code":
                "ES_QUOTE_TIMESTAMP_IN_FUTURE",
            "quote_age_seconds":
                round(age_seconds, 3),
            "updated_at":
                updated_at.isoformat(),
        }

    if (
        age_seconds
        > float(max_age_seconds)
    ):
        return {
            "available": False,
            "healthy": False,
            "reason_code":
                "ES_QUOTE_STALE",
            "quote_age_seconds":
                round(age_seconds, 3),
            "max_age_seconds":
                max_age_seconds,
            "updated_at":
                updated_at.isoformat(),
        }

    return {
        "available": True,
        "healthy": True,
        "reason_code":
            "ES_QUOTE_HEALTHY",
        "quote_age_seconds":
            round(
                max(
                    age_seconds,
                    0.0,
                ),
                3,
            ),
        "max_age_seconds":
            max_age_seconds,
        "updated_at":
            updated_at.isoformat(),
    }
