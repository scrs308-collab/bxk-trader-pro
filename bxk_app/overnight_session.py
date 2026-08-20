from datetime import datetime, time
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")


def get_spx_gth_session(
    now: datetime | None = None,
):
    """
    Return the SPX Global Trading Hours session state.

    Observation only.

    GTH window:
      8:15 PM ET through 9:25 AM ET

    This deliberately remains separate from the
    application's existing regular-market status.
    """

    if now is None:
        now = datetime.now(EASTERN)

    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=EASTERN
        )

    else:
        now = now.astimezone(
            EASTERN
        )

    weekday = now.weekday()
    clock = now.time().replace(
        tzinfo=None
    )

    evening_start = time(20, 15)
    morning_end = time(9, 25)

    # Saturday has no SPX GTH session.
    if weekday == 5:
        active = False

    # Sunday evening opens the Monday session.
    elif weekday == 6:
        active = clock >= evening_start

    # Monday through Thursday:
    # morning continuation + evening next-session opening.
    elif weekday in {0, 1, 2, 3}:
        active = (
            clock < morning_end
            or clock >= evening_start
        )

    # Friday only has the morning continuation.
    else:
        active = clock < morning_end

    if active:
        state = "GTH"
        reason_code = "SPX_GTH_ACTIVE"
    else:
        state = "INACTIVE"
        reason_code = "SPX_GTH_INACTIVE"

    return {
        "active": active,
        "state": state,
        "reason_code": reason_code,
        "eastern_time": now.isoformat(
            timespec="seconds"
        ),
    }
