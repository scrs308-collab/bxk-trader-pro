from datetime import datetime, timezone

from bxk_app.overnight_reference import (
    evaluate_future_quote_health,
)


NOW = datetime(
    2026,
    8,
    20,
    13,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_fresh_es_quote_is_healthy():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:11:45Z",
            "is-trading-halted": False,
        },
        as_of=NOW,
    )

    assert result["healthy"] is True
    assert (
        result["reason_code"]
        == "ES_QUOTE_HEALTHY"
    )
    assert (
        result["quote_age_seconds"]
        == 15
    )


def test_stale_es_quote_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:00:00Z",
            "is-trading-halted": False,
        },
        as_of=NOW,
        max_age_seconds=120,
    )

    assert result["healthy"] is False
    assert (
        result["reason_code"]
        == "ES_QUOTE_STALE"
    )


def test_halted_es_quote_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:11:55Z",
            "is-trading-halted": True,
        },
        as_of=NOW,
    )

    assert result["healthy"] is False
    assert (
        result["reason_code"]
        == "ES_QUOTE_HALTED"
    )


def test_missing_timestamp_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "is-trading-halted": False,
        },
        as_of=NOW,
    )

    assert result["healthy"] is False
    assert (
        result["reason_code"]
        == "ES_QUOTE_TIMESTAMP_UNAVAILABLE"
    )


def test_future_timestamp_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:12:30Z",
            "is-trading-halted": False,
        },
        as_of=NOW,
    )

    assert result["healthy"] is False
    assert (
        result["reason_code"]
        == "ES_QUOTE_TIMESTAMP_IN_FUTURE"
    )


def test_naive_quote_timestamp_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:11:45",
            "is-trading-halted": False,
        },
        as_of=NOW,
    )

    assert result["healthy"] is False

    assert (
        result["reason_code"]
        == "ES_QUOTE_TIMESTAMP_UNAVAILABLE"
    )


def test_naive_as_of_fails_closed():
    result = evaluate_future_quote_health(
        quote={
            "updated-at":
                "2026-08-20T13:11:45Z",
            "is-trading-halted": False,
        },
        as_of=datetime(
            2026,
            8,
            20,
            13,
            12,
            0,
        ),
    )

    assert result["healthy"] is False

    assert (
        result["reason_code"]
        == "ES_QUOTE_AS_OF_INVALID"
    )
