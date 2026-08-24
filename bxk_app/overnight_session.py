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
    monitoring_evening_start = time(18, 0)
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

    # -------------------------------------------------
    # Overnight Risk Guard monitoring window.
    #
    # ES futures begin trading at 6:00 PM ET.
    # Between 6:00 PM and the 8:15 PM SPX GTH open,
    # BXK may observe ES and calculate overnight risk,
    # but SPX GTH itself remains inactive.
    #
    # Daytime RTH is deliberately excluded because
    # this state is specifically for overnight risk.
    # -------------------------------------------------

    if weekday == 5:
        overnight_monitoring_active = False

    elif weekday == 6:
        overnight_monitoring_active = (
            clock >= monitoring_evening_start
        )

    elif weekday in {0, 1, 2, 3}:
        overnight_monitoring_active = (
            clock < morning_end
            or clock >= monitoring_evening_start
        )

    else:
        overnight_monitoring_active = (
            clock < morning_end
        )

    if active:
        state = "GTH"
        reason_code = "SPX_GTH_ACTIVE"

    else:
        state = "INACTIVE"
        reason_code = "SPX_GTH_INACTIVE"

    if active:
        monitoring_state = "GTH"

    elif overnight_monitoring_active:
        monitoring_state = "ES_ONLY"

    else:
        monitoring_state = "INACTIVE"

    return {
        "active": active,
        "state": state,
        "reason_code": reason_code,
        "overnight_monitoring_active":
            overnight_monitoring_active,
        "monitoring_state":
            monitoring_state,
        "eastern_time": now.isoformat(
            timespec="seconds"
        ),
    }
