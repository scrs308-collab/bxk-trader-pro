from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from bxk_app.overnight_baseline import (
    build_overnight_baseline,
    load_overnight_baseline,
    save_overnight_baseline,
)


ET = ZoneInfo("America/New_York")


def close_time(
    day,
    second=5,
):
    return datetime(
        2026,
        8,
        day,
        16,
        0,
        second,
        tzinfo=ET,
    )


def test_build_baseline():
    result = build_overnight_baseline(
        spx_close=7707.98,
        es_anchor_price=7729.0,
        es_symbol="/ESU6",
        captured_at=close_time(20),
    )

    assert (
        result["trading_date"]
        == "2026-08-20"
    )

    assert result["spx_close"] == 7707.98
    assert result["es_anchor_price"] == 7729.0
    assert result["es_symbol"] == "/ESU6"

    assert (
        result["reference_source"]
        == "RTH_CLOSE_SNAPSHOT"
    )


def test_invalid_spx_fails():
    with pytest.raises(ValueError):
        build_overnight_baseline(
            spx_close=None,
            es_anchor_price=7729,
            es_symbol="/ESU6",
            captured_at=close_time(20),
        )


def test_invalid_es_fails():
    with pytest.raises(ValueError):
        build_overnight_baseline(
            spx_close=7707.98,
            es_anchor_price=None,
            es_symbol="/ESU6",
            captured_at=close_time(20),
        )


def test_save_and_load_round_trip(
    tmp_path,
):
    save_overnight_baseline(
        spx_close=7707.98,
        es_anchor_price=7729.0,
        es_symbol="/ESU6",
        captured_at=close_time(20),
        directory=tmp_path,
    )

    result = load_overnight_baseline(
        trading_date="2026-08-20",
        directory=tmp_path,
    )

    assert result is not None
    assert result["spx_close"] == 7707.98
    assert result["es_symbol"] == "/ESU6"


def test_latest_same_day_capture_wins(
    tmp_path,
):
    save_overnight_baseline(
        spx_close=7705,
        es_anchor_price=7725,
        es_symbol="/ESU6",
        captured_at=close_time(
            20,
            second=1,
        ),
        directory=tmp_path,
    )

    save_overnight_baseline(
        spx_close=7707.98,
        es_anchor_price=7729,
        es_symbol="/ESU6",
        captured_at=close_time(
            20,
            second=45,
        ),
        directory=tmp_path,
    )

    result = load_overnight_baseline(
        trading_date="2026-08-20",
        directory=tmp_path,
    )

    assert result["spx_close"] == 7707.98
    assert result["es_anchor_price"] == 7729


def test_latest_date_is_loaded(
    tmp_path,
):
    save_overnight_baseline(
        spx_close=7700,
        es_anchor_price=7720,
        es_symbol="/ESU6",
        captured_at=close_time(19),
        directory=tmp_path,
    )

    save_overnight_baseline(
        spx_close=7707.98,
        es_anchor_price=7729,
        es_symbol="/ESU6",
        captured_at=close_time(20),
        directory=tmp_path,
    )

    result = load_overnight_baseline(
        directory=tmp_path,
    )

    assert (
        result["trading_date"]
        == "2026-08-20"
    )


def test_corrupt_file_fails_closed(
    tmp_path,
):
    path = (
        tmp_path
        / "2026-08-20.json"
    )

    path.write_text(
        "{ definitely not json",
        encoding="utf-8",
    )

    result = load_overnight_baseline(
        directory=tmp_path,
    )

    assert result is None
