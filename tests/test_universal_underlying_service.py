from bxk_app import (
    universal_underlying_service
    as service,
)


def chain(
    *,
    delivery_type,
    amount,
    symbol="TEST",
    dte=0,
):
    deliverable = {
        "amount": str(amount),
        "deliverable-type":
            delivery_type,
        "percent": "100",
        "root-symbol": symbol,
    }

    if delivery_type == "Shares":
        deliverable.update(
            {
                "instrument-type":
                    "Equity",
                "symbol": symbol,
            }
        )

    return {
        "data": {
            "items": [
                {
                    "underlying-symbol":
                        symbol,
                    "root-symbol":
                        symbol,
                    "option-chain-type":
                        "Standard",
                    "shares-per-contract":
                        100,
                    "deliverables": [
                        deliverable
                    ],
                    "expirations": [
                        {
                            "expiration-date":
                                "2026-08-19",
                            "days-to-expiration":
                                dte,
                            "settlement-type":
                                "PM",
                            "expiration-type":
                                "Weekly",
                            "strikes": [
                                {},
                                {},
                            ],
                        }
                    ],
                }
            ]
        }
    }


def quote(symbol):
    return {
        "symbol": symbol,
        "last": "100.25",
        "instrument-type":
            "Equity",
    }


def patch_quote(monkeypatch, symbol):
    monkeypatch.setattr(
        service.tastytrade_api,
        "get_equity_quote",
        lambda value: quote(value),
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_index_quote",
        lambda value: quote(value),
    )


def test_cash_delivery_is_discovered(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "XSP",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: chain(
            delivery_type="Cash",
            amount=0,
            symbol=value,
        ),
    )

    result = (
        service.discover_underlying(
            "XSP"
        )
    )

    assert (
        result["delivery_style"]
        == "CASH"
    )

    assert (
        result["instrument_family"]
        == "CASH_SETTLED_OPTION_UNDERLYING"
    )

    assert result["options_available"] is True
    assert result["has_0dte"] is True
    assert result["execution_enabled"] is False


def test_share_delivery_is_discovered(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "SPY",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: chain(
            delivery_type="Shares",
            amount=100,
            symbol=value,
        ),
    )

    result = (
        service.discover_underlying(
            "SPY"
        )
    )

    assert (
        result["delivery_style"]
        == "SHARES"
    )

    assert (
        result["instrument_family"]
        == "SHARE_SETTLED_OPTION_UNDERLYING"
    )

    assert result["analysis_enabled"] is True
    assert result["execution_enabled"] is False


def test_non_zero_nearest_expiration(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "DIA",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: chain(
            delivery_type="Shares",
            amount=100,
            symbol=value,
            dte=2,
        ),
    )

    result = (
        service.discover_underlying(
            "DIA"
        )
    )

    assert result["has_0dte"] is False

    assert (
        result[
            "nearest_expiration"
        ]["dte"]
        == 2
    )


def test_known_profile_enriches_qqq(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "QQQ",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: chain(
            delivery_type="Shares",
            amount=100,
            symbol=value,
        ),
    )

    result = (
        service.discover_underlying(
            "QQQ"
        )
    )

    assert (
        result["verified_profile"]
        is True
    )

    assert (
        result["exercise_style"]
        == "AMERICAN"
    )

    assert (
        result[
            "early_assignment_risk"
        ]
        is True
    )


def test_unknown_symbol_does_not_guess_exercise_style(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "ABC",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: chain(
            delivery_type="Shares",
            amount=100,
            symbol=value,
        ),
    )

    result = (
        service.discover_underlying(
            "ABC"
        )
    )

    assert (
        result["verified_profile"]
        is False
    )

    assert (
        result["exercise_style"]
        == "UNKNOWN"
    )

    assert (
        result[
            "early_assignment_risk"
        ]
        is None
    )

    assert result["execution_enabled"] is False


def test_missing_chain_fails_closed(
    monkeypatch,
):
    patch_quote(
        monkeypatch,
        "ABC",
    )

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda value: {},
    )

    result = (
        service.discover_underlying(
            "ABC"
        )
    )

    assert result["quote_available"] is True
    assert result["options_available"] is False
    assert result["analysis_enabled"] is False
    assert result["execution_enabled"] is False

    assert (
        result["reason_code"]
        == "OPTION_CHAIN_UNAVAILABLE"
    )
