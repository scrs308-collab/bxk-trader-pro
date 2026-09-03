from bxk_app.position_monitor import (
    build_position_summaries,
)


def _leg(
    symbol,
    direction,
    quantity,
    open_price=2.00,
    current_price=1.50,
):
    return {
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "multiplier": 100,
        "average_open_price": open_price,
        "current_price": current_price,
    }


def test_three_mixed_quantity_verticals_are_all_supported():
    """
    Reproduces the rolled SPX position from 9/3/2026:

    6x 7680/7700 put vertical
    4x 7755/7780 call vertical
    2x 7800/7825 call vertical
    """

    positions = [
        _leg(
            "SPXW  260904P07680000",
            "LONG",
            6,
            2.75,
            2.67,
        ),
        _leg(
            "SPXW  260904P07700000",
            "SHORT",
            6,
            4.60,
            4.45,
        ),
        _leg(
            "SPXW  260904C07755000",
            "SHORT",
            4,
            19.50,
            18.60,
        ),
        _leg(
            "SPXW  260904C07780000",
            "LONG",
            4,
            8.45,
            7.80,
        ),
        _leg(
            "SPXW  260904C07800000",
            "SHORT",
            2,
            3.60,
            3.25,
        ),
        _leg(
            "SPXW  260904C07825000",
            "LONG",
            2,
            1.15,
            1.02,
        ),
    ]

    summaries = build_position_summaries(
        positions=positions,
        spx_price=7753.14,
    )

    assert len(summaries) == 3

    strategies = {
        summary["strategy"]
        for summary in summaries
    }

    assert strategies == {
        "SPX Put Credit Spread",
        "SPX Call Credit Spread",
    }

    quantities = sorted(
        summary["quantity"]
        for summary in summaries
    )

    assert quantities == [2, 4, 6]

    for summary in summaries:
        assert len(summary["legs"]) == 2
        assert summary["position_type"] == "VERTICAL"


def test_single_calls_and_puts_are_supported():
    cases = [
        (
            _leg(
                "SPXW  260904C07800000",
                "LONG",
                2,
            ),
            "SPX Long Call",
        ),
        (
            _leg(
                "SPXW  260904C07800000",
                "SHORT",
                2,
            ),
            "SPX Short Call",
        ),
        (
            _leg(
                "SPXW  260904P07700000",
                "LONG",
                2,
            ),
            "SPX Long Put",
        ),
        (
            _leg(
                "SPXW  260904P07700000",
                "SHORT",
                2,
            ),
            "SPX Short Put",
        ),
    ]

    for leg, expected_strategy in cases:
        summaries = build_position_summaries(
            positions=[leg],
            spx_price=7753.14,
        )

        assert len(summaries) == 1

        summary = summaries[0]

        assert (
            summary["strategy"]
            == expected_strategy
        )

        assert (
            summary["position_type"]
            == "SINGLE"
        )

        assert len(summary["legs"]) == 1


def test_existing_iron_condor_still_groups_normally():
    positions = [
        _leg(
            "SPXW  260904P07650000",
            "LONG",
            4,
            1.00,
            0.75,
        ),
        _leg(
            "SPXW  260904P07675000",
            "SHORT",
            4,
            2.50,
            1.75,
        ),
        _leg(
            "SPXW  260904C07825000",
            "SHORT",
            4,
            2.50,
            1.75,
        ),
        _leg(
            "SPXW  260904C07850000",
            "LONG",
            4,
            1.00,
            0.75,
        ),
    ]

    summaries = build_position_summaries(
        positions=positions,
        spx_price=7753.14,
    )

    assert len(summaries) == 1

    summary = summaries[0]

    assert (
        summary["strategy"]
        == "SPX Iron Condor"
    )

    assert len(summary["legs"]) == 4
