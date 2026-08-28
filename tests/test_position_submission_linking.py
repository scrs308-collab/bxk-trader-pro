from bxk_app.services.position_service import (
    link_positions_to_submissions,
)


SYMBOLS = [
    "SPXW  260831P07650000",
    "SPXW  260831P07675000",
    "SPXW  260831C07815000",
    "SPXW  260831C07840000",
]


def _legs(symbols):
    return [
        {
            "symbol": symbol,
        }
        for symbol in symbols
    ]


def test_exact_symbols_link_position_to_submission():
    positions = [{
        "strategy": "SPX Iron Condor",
        "legs": _legs(reversed(SYMBOLS)),
    }]
    submissions = [{
        "timestamp_utc": "2026-08-28T14:30:00Z",
        "order_id": "ORDER-77",
        "order": {
            "limit_price": 2.74,
            "legs": _legs(SYMBOLS),
        },
    }]

    linked = link_positions_to_submissions(
        positions,
        submissions,
    )

    assert linked[0]["broker_linked"] is True
    assert linked[0]["broker_order_id"] == "ORDER-77"
    assert linked[0]["submitted_limit_credit"] == 2.74
    assert (
        linked[0]["submitted_at"]
        == "2026-08-28T14:30:00Z"
    )


def test_partial_symbol_match_does_not_link():
    positions = [{
        "legs": _legs(SYMBOLS),
    }]
    submissions = [{
        "order_id": "WRONG-ORDER",
        "order": {
            "legs": _legs(
                SYMBOLS[:3] + ["DIFFERENT SYMBOL"]
            ),
        },
    }]

    linked = link_positions_to_submissions(
        positions,
        submissions,
    )

    assert linked[0]["broker_linked"] is False
    assert "broker_order_id" not in linked[0]


def test_one_submission_links_only_one_position():
    positions = [
        {"legs": _legs(SYMBOLS)},
        {"legs": _legs(SYMBOLS)},
    ]
    submissions = [{
        "order_id": "ORDER-77",
        "order": {
            "legs": _legs(SYMBOLS),
        },
    }]

    linked = link_positions_to_submissions(
        positions,
        submissions,
    )

    assert linked[0]["broker_linked"] is True
    assert linked[1]["broker_linked"] is False
