import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")

DEFAULT_BASELINE_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "overnight_risk"
)


def _positive_float(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _eastern_datetime(
    value: datetime | None = None,
) -> datetime:
    if value is None:
        return datetime.now(EASTERN)

    if value.tzinfo is None:
        return value.replace(
            tzinfo=EASTERN
        )

    return value.astimezone(EASTERN)


def build_overnight_baseline(
    *,
    spx_close,
    es_anchor_price,
    es_symbol,
    captured_at=None,
):
    """
    Build one synchronized SPX / ES overnight baseline.

    This contains observation data only.
    """

    spx = _positive_float(spx_close)
    es = _positive_float(es_anchor_price)

    symbol = str(
        es_symbol or ""
    ).strip()

    if spx is None:
        raise ValueError(
            "SPX closing reference is required."
        )

    if es is None:
        raise ValueError(
            "ES anchor price is required."
        )

    if not symbol:
        raise ValueError(
            "ES symbol is required."
        )

    captured = _eastern_datetime(
        captured_at
    )

    return {
        "schema_version": 1,
        "trading_date":
            captured.date().isoformat(),
        "captured_at":
            captured.isoformat(
                timespec="seconds"
            ),
        "reference_source":
            "RTH_CLOSE_SNAPSHOT",
        "spx_close": round(
            spx,
            2,
        ),
        "es_anchor_price": round(
            es,
            3,
        ),
        "es_symbol": symbol,
    }


def save_overnight_baseline(
    *,
    spx_close,
    es_anchor_price,
    es_symbol,
    captured_at=None,
    directory=None,
):
    """
    Persist one baseline atomically.

    Repeated captures on the same trading date
    overwrite that date so the latest valid
    snapshot wins.
    """

    baseline = build_overnight_baseline(
        spx_close=spx_close,
        es_anchor_price=es_anchor_price,
        es_symbol=es_symbol,
        captured_at=captured_at,
    )

    target_dir = Path(
        directory
        if directory is not None
        else DEFAULT_BASELINE_DIR
    )

    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        target_dir
        / (
            baseline["trading_date"]
            + ".json"
        )
    )

    temporary = path.with_suffix(
        ".tmp"
    )

    temporary.write_text(
        json.dumps(
            baseline,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)

    return baseline


def _valid_loaded_baseline(value):
    if not isinstance(value, dict):
        return False

    required = (
        "trading_date",
        "captured_at",
        "spx_close",
        "es_anchor_price",
        "es_symbol",
    )

    if any(
        value.get(key) in (None, "")
        for key in required
    ):
        return False

    if _positive_float(
        value.get("spx_close")
    ) is None:
        return False

    if _positive_float(
        value.get("es_anchor_price")
    ) is None:
        return False

    return True


def load_overnight_baseline(
    *,
    trading_date=None,
    directory=None,
):
    """
    Load a specific baseline or the newest one.

    Invalid or corrupt storage fails closed
    by returning None.
    """

    target_dir = Path(
        directory
        if directory is not None
        else DEFAULT_BASELINE_DIR
    )

    if not target_dir.exists():
        return None

    if trading_date:
        candidates = [
            target_dir
            / f"{trading_date}.json"
        ]
    else:
        candidates = sorted(
            target_dir.glob("*.json"),
            reverse=True,
        )

    for path in candidates:
        if not path.exists():
            continue

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        if _valid_loaded_baseline(
            payload
        ):
            return payload

    return None
