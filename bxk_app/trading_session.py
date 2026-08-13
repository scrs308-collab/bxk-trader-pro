from datetime import datetime
from zoneinfo import ZoneInfo


MARKET_TIMEZONE = ZoneInfo("America/New_York")


def _market_time(
    now: datetime | None = None,
) -> datetime:
    """
    Normalize a datetime to the US market timezone.
    """

    if now is None:
        return datetime.now(
            MARKET_TIMEZONE
        )

    if now.tzinfo is None:
        return now.replace(
            tzinfo=MARKET_TIMEZONE
        )

    return now.astimezone(
        MARKET_TIMEZONE
    )


def get_spx_session(
    now: datetime | None = None,
) -> str:
    """
    Return the standard SPX trading session.

    Sessions:
        GTH    Global Trading Hours
        RTH    Regular Trading Hours
        CURB   Curb Trading Hours
        CLOSED No standard trading session

    Standard Eastern Time schedule:
        GTH    8:15 PM - 9:25 AM
        RTH    9:30 AM - 4:15 PM
        CURB   4:15 PM - 5:00 PM

    This models the normal weekly schedule.
    Exchange holidays or modified sessions must still
    fail closed through broker preflight.
    """

    market_now = _market_time(now)

    weekday = market_now.weekday()

    minutes = (
        market_now.hour * 60
        + market_now.minute
    )

    # ------------------------------------------
    # Overnight GTH
    # Monday through Friday mornings.
    # ------------------------------------------

    if (
        weekday in {0, 1, 2, 3, 4}
        and minutes < 565
    ):
        return "GTH"

    # ------------------------------------------
    # Regular Trading Hours
    # 9:30 AM - 4:15 PM ET
    # ------------------------------------------

    if (
        weekday in {0, 1, 2, 3, 4}
        and 570 <= minutes < 975
    ):
        return "RTH"

    # ------------------------------------------
    # Curb Trading Hours
    # 4:15 PM - 5:00 PM ET
    # ------------------------------------------

    if (
        weekday in {0, 1, 2, 3, 4}
        and 975 <= minutes < 1020
    ):
        return "CURB"

    # ------------------------------------------
    # Evening GTH
    # Sunday through Thursday evenings.
    # ------------------------------------------

    if (
        weekday in {6, 0, 1, 2, 3}
        and minutes >= 1215
    ):
        return "GTH"

    return "CLOSED"


def get_spx_execution_policy(
    now: datetime | None = None,
) -> dict:
    """
    Return conservative BXK execution-session policy.

    BXK currently builds DAY orders. Therefore only RTH
    is eligible for the existing execution path.

    GTH/CURB are recognized but require an extended-hours
    order implementation before BXK may submit there.
    """

    market_now = _market_time(now)

    session = get_spx_session(
        market_now
    )

    return {
        "session": session,
        "market_time": (
            market_now.isoformat(
                timespec="seconds"
            )
        ),
        "session_open": (
            session
            in {"RTH", "CURB", "GTH"}
        ),
        "day_order_allowed": (
            session == "RTH"
        ),
        "extended_order_required": (
            session in {"CURB", "GTH"}
        ),
    }
