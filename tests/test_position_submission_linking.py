from bxk_app.services.position_service import (
    link_positions_to_journals,
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

def test_exact_symbols_link_position_to_journal():
    positions = [{
        "strategy": "SPX Iron Condor",
        "legs": _legs(
            reversed(
                SYMBOLS
            )
        ),
        "broker_linked": False,
    }]

    journals = [{
        "broker_order_id":
            "JOURNAL-501237249",
        "submitted_at":
            "2026-09-01T15:35:45+00:00",
        "submitted_limit_credit":
            2.20,
        "symbols":
            list(SYMBOLS),
    }]

    linked = link_positions_to_journals(
        positions,
        journals,
    )

    assert (
        linked[0]["broker_linked"]
        is True
    )

    assert (
        linked[0]["broker_order_id"]
        == "JOURNAL-501237249"
    )

    assert (
        linked[0]["broker_link_source"]
        == "TRADE_JOURNAL"
    )

    assert (
        linked[0][
            "submitted_limit_credit"
        ]
        == 2.20
    )


def test_ambiguous_journal_match_does_not_link():
    positions = [{
        "legs": _legs(
            SYMBOLS
        ),
        "broker_linked": False,
    }]

    journals = [
        {
            "broker_order_id":
                "JOURNAL-A",
            "symbols":
                list(SYMBOLS),
        },
        {
            "broker_order_id":
                "JOURNAL-B",
            "symbols":
                list(SYMBOLS),
        },
    ]

    linked = link_positions_to_journals(
        positions,
        journals,
    )

    assert (
        linked[0]["broker_linked"]
        is False
    )

    assert (
        "broker_order_id"
        not in linked[0]
    )


def test_execution_audit_link_is_not_replaced_by_journal():
    positions = [{
        "legs": _legs(
            SYMBOLS
        ),
    }]

    submissions = [{
        "order_id":
            "AUDIT-ORDER",
        "order": {
            "legs":
                _legs(
                    SYMBOLS
                ),
        },
    }]

    journals = [{
        "broker_order_id":
            "JOURNAL-ORDER",
        "symbols":
            list(SYMBOLS),
    }]

    audited = (
        link_positions_to_submissions(
            positions,
            submissions,
        )
    )

    linked = (
        link_positions_to_journals(
            audited,
            journals,
        )
    )

    assert (
        linked[0]["broker_order_id"]
        == "AUDIT-ORDER"
    )

    assert (
        linked[0]["broker_link_source"]
        == "EXECUTION_AUDIT"
    )
