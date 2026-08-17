from datetime import datetime


MARKET_OPEN_MINUTE = 9 * 60 + 30
MARKET_CLOSE_MINUTE = 16 * 60


def get_market_session_phase(now=None):
    """
    Classify the regular SPX trading session.

    Phases:
        OPENING    09:30 - 09:59
        EARLY      10:00 - 10:59
        MIDDAY     11:00 - 13:59
        AFTERNOON  14:00 - 14:59
        LATE       15:00 - 15:59
        CLOSED     Outside regular session / weekend

    Times currently follow the same local-time convention used
    elsewhere in BXK.
    """

    current = now or datetime.now()

    if current.weekday() >= 5:
        return {
            "session_phase": "CLOSED",
            "minutes_since_open": None,
        }

    current_minute = (
        current.hour * 60 +
        current.minute
    )

    if (
        current_minute < MARKET_OPEN_MINUTE
        or current_minute >= MARKET_CLOSE_MINUTE
    ):
        return {
            "session_phase": "CLOSED",
            "minutes_since_open": None,
        }

    minutes_since_open = (
        current_minute -
        MARKET_OPEN_MINUTE
    )

    if minutes_since_open < 30:
        phase = "OPENING"
    elif minutes_since_open < 90:
        phase = "EARLY"
    elif minutes_since_open < 270:
        phase = "MIDDAY"
    elif minutes_since_open < 330:
        phase = "AFTERNOON"
    else:
        phase = "LATE"

    return {
        "session_phase": phase,
        "minutes_since_open": minutes_since_open,
    }
