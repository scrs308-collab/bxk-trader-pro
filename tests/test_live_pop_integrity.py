import math
import re
from pathlib import Path

import bxk_app.execution_engine as execution_engine
import bxk_app.scanner_engine as scanner_engine


def get_execution_validator():
    classes = []

    for value in vars(
        execution_engine
    ).values():
        if (
            isinstance(value, type)
            and value.__module__
            == execution_engine.__name__
            and hasattr(value, "validate_pop")
        ):
            classes.append(value)

    assert len(classes) == 1

    return classes[0].__new__(
        classes[0]
    )


def test_no_hardcoded_pop_placeholders():
    pattern = re.compile(
        r'["\\\']pop["\\\']\\s*:\\s*(?:84|85)'
        r'|\\[\\s*["\\\']pop["\\\']\\s*\\]'
        r'\\s*=\\s*(?:84|85)'
    )

    offenders = []

    for path in Path(
        "bxk_app"
    ).rglob("*.py"):
        body = path.read_text(
            encoding="utf-8"
        )

        if pattern.search(body):
            offenders.append(
                str(path)
            )

    assert offenders == []


def test_condor_pop_uses_both_short_deltas():
    source = Path(
        "bxk_app/live_option_engine.py"
    ).read_text(
        encoding="utf-8"
    )

    start = source.index(
        "def calculate_probability_metrics"
    )

    end = source.find(
        "\ndef ",
        start + 10,
    )

    block = (
        source[start:end]
        if end != -1
        else source[start:]
    )

    assert "- put_delta" in block
    assert "- call_delta" in block
    assert "1\n                    - put_delta" in block


def test_scanner_propagates_live_pop(
    monkeypatch,
):
    live_result = {
        "live_credit": 2.0,
        "put_credit": 1.0,
        "call_credit": 1.0,
        "sell_put_mid": 1.1,
        "buy_put_mid": 0.1,
        "sell_call_mid": 1.1,
        "buy_call_mid": 0.1,
        "pop": 72.5,
    }

    monkeypatch.setattr(
        scanner_engine,
        "calculate_iron_condor_credit",
        lambda trade: live_result,
    )

    monkeypatch.setattr(
        scanner_engine,
        "score_candidate",
        lambda trade: 88,
    )

    trade = {
        "wing_width": 25,
    }

    result = scanner_engine.enrich_candidate(
        trade
    )

    assert result["pop"] == 72.5


def test_scanner_preserves_missing_pop(
    monkeypatch,
):
    live_result = {
        "live_credit": 2.0,
        "put_credit": 1.0,
        "call_credit": 1.0,
        "sell_put_mid": 1.1,
        "buy_put_mid": 0.1,
        "sell_call_mid": 1.1,
        "buy_call_mid": 0.1,
        "pop": None,
    }

    monkeypatch.setattr(
        scanner_engine,
        "calculate_iron_condor_credit",
        lambda trade: live_result,
    )

    monkeypatch.setattr(
        scanner_engine,
        "score_candidate",
        lambda trade: 50,
    )

    result = scanner_engine.enrich_candidate(
        {
            "wing_width": 25,
        }
    )

    assert result["pop"] is None


def test_execution_pop_gate_fails_closed():
    validator = get_execution_validator()

    for value in (
        None,
        "",
        "garbage",
        math.nan,
        math.inf,
        -1,
        101,
    ):
        assert validator.validate_pop(
            {"pop": value}
        ) == (
            False,
            "POP unavailable",
        )

    assert validator.validate_pop(
        {}
    ) == (
        False,
        "POP unavailable",
    )

    assert validator.validate_pop(
        {"pop": 59.9}
    ) == (
        False,
        "POP below minimum",
    )

    assert validator.validate_pop(
        {"pop": 60}
    ) == (
        True,
        "",
    )

    assert validator.validate_pop(
        {"pop": "72.5"}
    ) == (
        True,
        "",
    )
