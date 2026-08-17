import csv
from pathlib import Path


CHECKPOINTS = {
    "0945": 15,
    "1000": 30,
    "1030": 60,
}


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_rows(path):
    path = Path(path)

    if not path.exists():
        return []

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            rows.append(row)

    return rows


def _checkpoint_row(
    rows,
    checkpoint_minute,
    *,
    tolerance_minutes=2,
):
    for row in rows:
        minute = _to_int(
            row.get("minutes_since_open")
        )

        if minute is None:
            continue

        if (
            checkpoint_minute
            <= minute
            <= checkpoint_minute + tolerance_minutes
        ):
            return row

    return None


def summarize_condor_risk_day(path):
    """
    Build a compact diagnostic summary from one completed
    Condor Stability trading-day CSV.

    Observation-only. No trade decision is produced here.
    """

    path = Path(path)
    rows = _load_rows(path)

    if not rows:
        return {
            "available": False,
            "status": "NO_DATA",
            "date": path.stem,
        }

    implied_values = [
        value
        for value in (
            _to_float(
                row.get("expected_move")
            )
            for row in rows
        )
        if value is not None and value > 0
    ]

    if not implied_values:
        return {
            "available": False,
            "status": "IMPLIED_MOVE_UNAVAILABLE",
            "date": path.stem,
        }

    opening_implied_move = implied_values[0]

    session_ranges = [
        value
        for value in (
            _to_float(
                row.get("session_range")
            )
            for row in rows
        )
        if value is not None
    ]

    directional_values = [
        value
        for value in (
            _to_float(
                row.get(
                    "max_directional_excursion"
                )
            )
            for row in rows
        )
        if value is not None
    ]

    directional_pct_values = [
        value
        for value in (
            _to_float(
                row.get(
                    "directional_consumed_pct"
                )
            )
            for row in rows
        )
        if value is not None
    ]

    pressure_rows = []

    for row in rows:
        pressure = _to_float(
            row.get("pressure_ratio")
        )

        if pressure is None:
            continue

        pressure_rows.append(
            (pressure, row)
        )

    peak_pressure = None
    peak_pressure_timestamp = None
    peak_pressure_minute = None

    if pressure_rows:
        peak_pressure, peak_row = max(
            pressure_rows,
            key=lambda item: item[0],
        )

        peak_pressure_timestamp = (
            peak_row.get("timestamp")
        )

        peak_pressure_minute = _to_int(
            peak_row.get(
                "minutes_since_open"
            )
        )

    final_session_range = max(
        session_ranges,
        default=0.0,
    )

    max_directional = max(
        directional_values,
        default=0.0,
    )

    max_directional_pct = max(
        directional_pct_values,
        default=0.0,
    )

    expansion_ratio = (
        max_directional /
        opening_implied_move
        if opening_implied_move > 0
        else 0.0
    )

    checkpoints = {}

    for label, minute in CHECKPOINTS.items():
        row = _checkpoint_row(
            rows,
            minute,
        )

        if row is None:
            checkpoints[label] = {
                "available": False,
            }

            continue

        checkpoints[label] = {
            "available": True,
            "actual_minute": _to_int(
                row.get(
                    "minutes_since_open"
                )
            ),
            "spx": _to_float(
                row.get("spx")
            ),
            "directional_consumed_pct":
                _to_float(
                    row.get(
                        "directional_consumed_pct"
                    )
                ),
            "expected_pace_pct":
                _to_float(
                    row.get(
                        "expected_pace_pct"
                    )
                ),
            "pressure_ratio":
                _to_float(
                    row.get(
                        "pressure_ratio"
                    )
                ),
        }

    return {
        "available": True,
        "status": "AVAILABLE",
        "date": path.stem,
        "observation_count": len(rows),
        "opening_implied_move": round(
            opening_implied_move,
            2,
        ),
        "final_session_range": round(
            final_session_range,
            2,
        ),
        "max_directional_excursion": round(
            max_directional,
            2,
        ),
        "max_directional_consumed_pct": round(
            max_directional_pct,
            1,
        ),
        "expansion_ratio": round(
            expansion_ratio,
            2,
        ),
        "peak_pressure_ratio": (
            round(peak_pressure, 2)
            if peak_pressure is not None
            else None
        ),
        "peak_pressure_timestamp":
            peak_pressure_timestamp,
        "peak_pressure_minute":
            peak_pressure_minute,
        "checkpoints": checkpoints,
    }
