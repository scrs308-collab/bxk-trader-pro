from __future__ import annotations

from typing import Any

from bxk_app.broker_tastytrade import (
    tastytrade_api,
)
from bxk_app.underlyings import (
    UNDERLYINGS,
)


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()

    if not value:
        raise ValueError(
            "Underlying symbol is required."
        )

    return value


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_price(
    quote: dict[str, Any] | None,
):
    if not isinstance(quote, dict):
        return None

    for key in (
        "last",
        "mark",
        "mid",
        "last-price",
    ):
        value = _safe_float(
            quote.get(key)
        )

        if value is not None and value > 0:
            return value

    bid = _safe_float(
        quote.get("bid")
    )

    ask = _safe_float(
        quote.get("ask")
    )

    if (
        bid is not None
        and ask is not None
        and bid > 0
        and ask > 0
    ):
        return round(
            (bid + ask) / 2.0,
            4,
        )

    return None


def _get_quote(symbol: str):
    """
    Quote endpoints are not used to classify instruments.

    Tasty may return equity-shaped market data from more
    than one endpoint, including for index products.
    """

    errors = []

    for getter in (
        tastytrade_api.get_equity_quote,
        tastytrade_api.get_index_quote,
    ):
        try:
            quote = getter(symbol)

            if isinstance(quote, dict):
                price = _extract_price(
                    quote
                )

                if price is not None:
                    return quote, price

        except Exception as exc:
            errors.append(str(exc))

    return None, None


def _extract_chain_items(
    response: dict[str, Any] | None,
):
    if not isinstance(response, dict):
        return []

    items = response.get("items")

    if isinstance(items, list):
        return items

    data = response.get("data")

    if isinstance(data, dict):
        items = data.get("items")

        if isinstance(items, list):
            return items

    return []


def _delivery_style(
    deliverables,
):
    if not isinstance(deliverables, list):
        return "UNKNOWN"

    delivery_types = {
        str(
            item.get(
                "deliverable-type",
                "",
            )
        ).strip().upper()
        for item in deliverables
        if isinstance(item, dict)
    }

    delivery_types.discard("")

    has_cash = "CASH" in delivery_types
    has_shares = "SHARES" in delivery_types

    if has_cash and not has_shares:
        return "CASH"

    if has_shares and not has_cash:
        return "SHARES"

    if has_cash and has_shares:
        return "MIXED"

    return "UNKNOWN"


def _instrument_family(
    delivery_style: str,
):
    if delivery_style == "CASH":
        return (
            "CASH_SETTLED_OPTION_UNDERLYING"
        )

    if delivery_style == "SHARES":
        return (
            "SHARE_SETTLED_OPTION_UNDERLYING"
        )

    if delivery_style == "MIXED":
        return (
            "COMPLEX_OPTION_UNDERLYING"
        )

    return "UNKNOWN_OPTION_UNDERLYING"


def _normalize_expirations(
    expirations,
):
    result = []

    if not isinstance(expirations, list):
        return result

    for expiration in expirations:
        if not isinstance(expiration, dict):
            continue

        strikes = expiration.get(
            "strikes",
            [],
        )

        dte = _safe_int(
            expiration.get(
                "days-to-expiration"
            )
        )

        result.append(
            {
                "expiration_date":
                    expiration.get(
                        "expiration-date"
                    ),
                "dte": dte,
                "expiration_type":
                    expiration.get(
                        "expiration-type"
                    ),
                "settlement_type":
                    expiration.get(
                        "settlement-type"
                    ),
                "strike_count": (
                    len(strikes)
                    if isinstance(
                        strikes,
                        list,
                    )
                    else 0
                ),
            }
        )

    result.sort(
        key=lambda item: (
            (
                item["dte"]
                if item["dte"] is not None
                else 999999
            ),
            str(
                item.get(
                    "expiration_date"
                )
                or ""
            ),
        )
    )

    return result


def discover_underlying(
    symbol: str,
):
    """
    Discover an optionable underlying using broker data.

    This is observation/discovery only.

    Discovery never authorizes order execution.
    """

    symbol = normalize_symbol(symbol)

    quote, price = _get_quote(
        symbol
    )

    try:
        chain_response = (
            tastytrade_api
            .get_nested_option_chain(
                symbol
            )
        )
    except Exception:
        chain_response = None

    items = _extract_chain_items(
        chain_response
    )

    root = (
        items[0]
        if items
        else {}
    )

    deliverables = root.get(
        "deliverables",
        [],
    )

    delivery_style = _delivery_style(
        deliverables
    )

    instrument_family = (
        _instrument_family(
            delivery_style
        )
    )

    expirations = (
        _normalize_expirations(
            root.get(
                "expirations",
                [],
            )
        )
    )

    options_available = (
        len(expirations) > 0
    )

    quote_available = (
        price is not None
    )

    nearest_expiration = (
        expirations[0]
        if expirations
        else None
    )

    has_0dte = any(
        item.get("dte") == 0
        for item in expirations
    )

    profile = UNDERLYINGS.get(
        symbol
    )

    verified_profile = (
        profile is not None
    )

    if profile is not None:
        exercise_style = (
            profile.exercise_style
        )

        early_assignment_risk = (
            profile.early_assignment_risk
        )

        configured_instrument_type = (
            profile.instrument_type
        )

        expected_move_method = (
            profile.expected_move_method
        )

        default_wing_width = (
            profile.default_wing_width
        )

        volatility_reference = (
            profile.volatility_reference
        )

    else:
        # Do not guess exercise style.
        #
        # A share deliverable strongly identifies physical
        # settlement but does not, by itself, prove whether
        # exercise is American or European.
        exercise_style = "UNKNOWN"

        early_assignment_risk = None

        configured_instrument_type = (
            None
        )

        expected_move_method = (
            "OPTION_CHAIN"
        )

        default_wing_width = None

        volatility_reference = None

    if (
        quote_available
        and options_available
    ):
        reason_code = "DISCOVERY_READY"

    elif not quote_available:
        reason_code = (
            "UNDERLYING_QUOTE_UNAVAILABLE"
        )

    else:
        reason_code = (
            "OPTION_CHAIN_UNAVAILABLE"
        )

    return {
        "symbol": symbol,

        "quote_available":
            quote_available,

        "options_available":
            options_available,

        "price": price,

        "broker_instrument_type": (
            quote.get("instrument-type")
            if isinstance(
                quote,
                dict,
            )
            else None
        ),

        "instrument_family":
            instrument_family,

        "delivery_style":
            delivery_style,

        "deliverables":
            deliverables,

        "option_chain_type":
            root.get(
                "option-chain-type"
            ),

        "underlying_symbol":
            root.get(
                "underlying-symbol"
            ),

        "root_symbol":
            root.get(
                "root-symbol"
            ),

        "shares_per_contract":
            _safe_int(
                root.get(
                    "shares-per-contract"
                )
            ),

        "expiration_count":
            len(expirations),

        "nearest_expiration":
            nearest_expiration,

        "has_0dte":
            has_0dte,

        "expirations":
            expirations,

        "verified_profile":
            verified_profile,

        "configured_instrument_type":
            configured_instrument_type,

        "exercise_style":
            exercise_style,

        "early_assignment_risk":
            early_assignment_risk,

        "expected_move_method":
            expected_move_method,

        "volatility_reference":
            volatility_reference,

        "default_wing_width":
            default_wing_width,

        # Discovery capability only.
        "analysis_enabled": (
            quote_available
            and options_available
        ),

        # Universal execution remains fail-closed.
        "execution_enabled": False,

        "reason_code":
            reason_code,
    }
