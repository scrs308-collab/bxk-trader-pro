from bxk_app.position_monitor import (
    assess_quote_quality,
    build_iron_condor_summary,
)


EXPIRATION = "2026-08-25T20:00:00.000Z"


def leg(
    *,
    symbol,
    direction,
    open_price,
    bid,
    ask,
):
    current_price = (
        bid + ask
    ) / 2

    quantity = 4
    multiplier = 100

    if direction == "SHORT":
        pnl = (
            open_price - current_price
        ) * quantity * multiplier
    else:
        pnl = (
            current_price - open_price
        ) * quantity * multiplier

    return {
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "multiplier": multiplier,
        "average_open_price": open_price,
        "current_price": current_price,
        "bid": bid,
        "ask": ask,
        "price_source": "live-mid",
        "pnl": round(pnl, 2),
        "expires_at": EXPIRATION,
    }


def normal_position():
    return [
        leg(
            symbol="SPXW  260825P07575000",
            direction="LONG",
            open_price=2.42,
            bid=0.75,
            ask=0.85,
        ),
        leg(
            symbol="SPXW  260825P07600000",
            direction="SHORT",
            open_price=4.33,
            bid=1.05,
            ask=1.15,
        ),
        leg(
            symbol="SPXW  260825C07700000",
            direction="SHORT",
            open_price=3.29,
            bid=2.75,
            ask=2.80,
        ),
        leg(
            symbol="SPXW  260825C07725000",
            direction="LONG",
            open_price=1.10,
            bid=0.95,
            ask=1.15,
        ),
    ]


def bad_opening_quotes():
    return [
        leg(
            symbol="SPXW  260825P07575000",
            direction="LONG",
            open_price=2.42,
            bid=4.00,
            ask=4.10,
        ),
        leg(
            symbol="SPXW  260825P07600000",
            direction="SHORT",
            open_price=4.33,
            bid=6.70,
            ask=6.85,
        ),
        leg(
            symbol="SPXW  260825C07700000",
            direction="SHORT",
            open_price=3.29,
            bid=4.30,
            ask=9.80,
        ),
        leg(
            symbol="SPXW  260825C07725000",
            direction="LONG",
            open_price=1.10,
            bid=0.95,
            ask=1.15,
        ),
    ]


def test_extremely_wide_quote_is_unreliable():
    quality = assess_quote_quality(
        bid=4.30,
        ask=9.80,
        current_price=7.05,
    )

    assert quality["quote_quality"] == "UNRELIABLE"
    assert quality["quote_reliable"] is False
    assert quality["quote_spread"] == 5.5


def test_normal_quotes_are_reliable():
    summary = build_iron_condor_summary(
        normal_position(),
        spx_price=7682.91,
    )

    assert summary is not None
    assert summary["quote_quality"] == "GOOD"
    assert summary["valuation_reliable"] is True
    assert summary["pnl_is_estimate"] is False
    assert summary["unreliable_legs"] == []


def test_bad_opening_quote_marks_pnl_as_estimate():
    summary = build_iron_condor_summary(
        bad_opening_quotes(),
        spx_price=7682.91,
    )

    assert summary is not None

    # Recreates the distorted midpoint calculation
    # observed during the bad Tastytrade market.
    assert abs(
        summary["current_debit"] - 8.725
    ) <= 0.01
    assert summary["pnl"] == -1850

    assert summary["quote_quality"] == "UNRELIABLE"
    assert summary["valuation_reliable"] is False
    assert summary["pnl_is_estimate"] is True

    assert "7700 CALL" in summary["unreliable_legs"]

    # The unreliable midpoint must not create an
    # automated P/L EXIT instruction.
    assert summary["status"] != "EXIT"

    assert (
        "loss has reached"
        not in summary["recommendation"].lower()
    )

    assert (
        summary["coach"]["recommendation"]
        != "EXIT POSITION"
    )

    assert (
        summary["coach"]["headline"]
        == "Option quote quality unreliable"
    )


def test_quote_guard_clears_when_market_normalizes():
    bad = build_iron_condor_summary(
        bad_opening_quotes(),
        spx_price=7682.91,
    )

    good = build_iron_condor_summary(
        normal_position(),
        spx_price=7682.91,
    )

    assert bad["valuation_reliable"] is False
    assert good["valuation_reliable"] is True

    assert bad["quote_quality"] == "UNRELIABLE"
    assert good["quote_quality"] == "GOOD"


def test_real_strike_breach_still_forces_exit():
    summary = build_iron_condor_summary(
        bad_opening_quotes(),
        spx_price=7702.00,
    )

    assert summary is not None
    assert summary["valuation_reliable"] is False

    # Quote quality must never suppress genuine
    # underlying-price danger.
    assert (
        summary["coach"]["recommendation"]
        == "EXIT POSITION"
    )

    assert (
        summary["coach"]["headline"]
        == "Short strike breached"
    )
