import csv
from datetime import datetime
from pathlib import Path
from threading import Lock

from bxk_app.market_session import (
    get_market_session_phase,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LOG_DIR = (
    PROJECT_ROOT /
    "data" /
    "condor_stability"
)

FIELDNAMES = [
    "timestamp",
    "session_phase",
    "minutes_since_open",
    "expected_pace_pct",
    "pressure_ratio",
    "pace_delta_pct",
    "spx",
    "vix",
    "vix1d",
    "expected_move",
    "session_open",
    "day_high",
    "day_low",
    "session_range",
    "upside_excursion",
    "downside_excursion",
    "max_directional_excursion",
    "directional_consumed_pct",
    "range_band_consumed_pct",
    "current_displacement",
    "current_displacement_pct",
    "overnight_gap",
    "overnight_gap_pct",
    "expected_move_source",
    "market_status",
    "signal_ready",
]

_log_lock = Lock()


def _clean(value):
    if value is None or value == "--":
        return ""

    return value


def _minute_key(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M")


def _last_logged_minute(path: Path):
    if not path.exists():
        return None

    last_row = None

    try:
        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)

            for row in reader:
                last_row = row
    except OSError:
        return None

    if not last_row:
        return None

    timestamp = last_row.get("timestamp")

    if not timestamp:
        return None

    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    return _minute_key(parsed)


def log_condor_stability(
    market_data,
    *,
    now=None,
    log_dir=None,
):
    """
    Persist one valid Condor Stability observation per minute.

    Logging occurs only when:
      - stability data is available
      - signal_ready is True
      - market status is LIVE
      - expected move source is VIX1D

    The logger is restart-safe and will not duplicate a minute that
    already exists in the daily CSV.
    """

    stability = getattr(
        market_data,
        "condor_stability",
        {},
    )

    if not isinstance(stability, dict):
        return {
            "logged": False,
            "reason": "STABILITY_DATA_UNAVAILABLE",
        }

    if stability.get("available") is not True:
        return {
            "logged": False,
            "reason": "STABILITY_DATA_UNAVAILABLE",
        }

    if stability.get("signal_ready") is not True:
        return {
            "logged": False,
            "reason": "SIGNAL_NOT_READY",
        }

    market_status = str(
        stability.get("market_status", "")
    ).upper()

    if market_status != "LIVE":
        return {
            "logged": False,
            "reason": "MARKET_NOT_LIVE",
        }

    expected_move_source = str(
        stability.get("expected_move_source", "")
    ).upper()

    if expected_move_source != "VIX1D":
        return {
            "logged": False,
            "reason": "VIX1D_UNAVAILABLE",
        }

    current_time = now or datetime.now()

    directory = Path(
        log_dir
        if log_dir is not None
        else DEFAULT_LOG_DIR
    )

    path = (
        directory /
        f"{current_time:%Y-%m-%d}.csv"
    )

    minute = _minute_key(current_time)

    session = get_market_session_phase(
        current_time
    )

    pressure = stability.get(
        "range_expansion_pressure",
        {},
    )

    row = {
        "timestamp": current_time.isoformat(
            timespec="seconds"
        ),
        "session_phase":
            session["session_phase"],
        "minutes_since_open":
            session["minutes_since_open"],
        "expected_pace_pct": _clean(
            pressure.get("expected_pace_pct")
        ),
        "pressure_ratio": _clean(
            pressure.get("pressure_ratio")
        ),
        "pace_delta_pct": _clean(
            pressure.get("pace_delta_pct")
        ),
        "spx": _clean(
            getattr(market_data, "spx", None)
        ),
        "vix": _clean(
            getattr(market_data, "vix", None)
        ),
        "vix1d": _clean(
            getattr(market_data, "vix1d", None)
        ),
        "expected_move": _clean(
            stability.get(
                "implied_move",
                getattr(
                    market_data,
                    "expected_move",
                    None,
                ),
            )
        ),
        "session_open": _clean(
            stability.get("session_open")
        ),
        "day_high": _clean(
            stability.get("day_high")
        ),
        "day_low": _clean(
            stability.get("day_low")
        ),
        "session_range": _clean(
            stability.get("session_range")
        ),
        "upside_excursion": _clean(
            stability.get("upside_excursion")
        ),
        "downside_excursion": _clean(
            stability.get("downside_excursion")
        ),
        "max_directional_excursion": _clean(
            stability.get(
                "max_directional_excursion"
            )
        ),
        "directional_consumed_pct": _clean(
            stability.get(
                "directional_consumed_pct"
            )
        ),
        "range_band_consumed_pct": _clean(
            stability.get(
                "range_band_consumed_pct"
            )
        ),
        "current_displacement": _clean(
            stability.get(
                "current_displacement"
            )
        ),
        "current_displacement_pct": _clean(
            stability.get(
                "current_displacement_pct"
            )
        ),
        "overnight_gap": _clean(
            stability.get("overnight_gap")
        ),
        "overnight_gap_pct": _clean(
            stability.get(
                "overnight_gap_pct"
            )
        ),
        "expected_move_source":
            expected_move_source,
        "market_status":
            market_status,
        "signal_ready":
            stability.get("signal_ready"),
    }

    try:
        with _log_lock:
            if _last_logged_minute(path) == minute:
                return {
                    "logged": False,
                    "reason": "MINUTE_ALREADY_LOGGED",
                    "path": str(path),
                }

            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            file_exists = path.exists()

            with path.open(
                "a",
                encoding="utf-8",
                newline="",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=FIELDNAMES,
                )

                if not file_exists:
                    writer.writeheader()

                writer.writerow(row)

    except OSError as exc:
        return {
            "logged": False,
            "reason": "LOG_WRITE_FAILED",
            "error": str(exc),
        }

    return {
        "logged": True,
        "reason": "LOGGED",
        "path": str(path),
        "minute": minute,
    }
