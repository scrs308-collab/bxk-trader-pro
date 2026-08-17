from pathlib import Path

from bxk_app.forward_move import (
    calculate_forward_profile,
    load_forward_history,
)
from bxk_app.range_expansion import (
    calculate_range_expansion_profile,
    load_range_expansion_history,
)


DEFAULT_HISTORY_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "condor_stability"
)


CHECKPOINTS = {
    "0945": 15,
    "1000": 30,
    "1030": 60,
}


def build_condor_risk_profile(
    *,
    current_implied_move=None,
    history_dir=None,
    history_limit=20,
):
    """
    Build one observation-only historical risk profile.

    This does NOT authorize or block trades.

    It combines:
      - full-session historical range expansion
      - forward movement after 09:45
      - forward movement after 10:00
      - forward movement after 10:30
    """

    directory = Path(
        history_dir
        if history_dir is not None
        else DEFAULT_HISTORY_DIR
    )

    range_history = (
        load_range_expansion_history(
            directory,
            limit=history_limit,
        )
    )

    range_profile = (
        calculate_range_expansion_profile(
            range_history,
            current_implied_move=
                current_implied_move,
        )
    )

    forward_profiles = {}

    for label, minute in CHECKPOINTS.items():
        history = load_forward_history(
            directory,
            minute,
            limit=history_limit,
        )

        profile = calculate_forward_profile(
            history,
            current_implied_move=
                current_implied_move,
        )

        profile["checkpoint_minute"] = minute
        forward_profiles[label] = profile

    sample_counts = [
        range_profile.get("sample_days", 0),
        *[
            profile.get("sample_days", 0)
            for profile
            in forward_profiles.values()
        ],
    ]

    max_samples = max(
        sample_counts,
        default=0,
    )

    min_samples = min(
        sample_counts,
        default=0,
    )

    if min_samples >= 10:
        status = "AVAILABLE"
    elif max_samples > 0:
        status = "OBSERVING"
    else:
        status = "INSUFFICIENT_HISTORY"

    return {
        "status": status,
        "history_directory": str(directory),
        "history_limit": history_limit,
        "sample_days": max_samples,
        "current_implied_move":
            current_implied_move,
        "range_expansion":
            range_profile,
        "forward_risk":
            forward_profiles,
    }
