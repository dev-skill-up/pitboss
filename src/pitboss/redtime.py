"""Reading ISO 8601 times from GitHub, and the seconds between them."""

import datetime


def moment(text: str) -> datetime.datetime:
    """Read an ISO 8601 time.

    Args:
        text: the time.

    Returns:
        It, timezone-aware (UTC when the text names none).
    """
    parsed = datetime.datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.UTC)


def seconds(start: str, end: str) -> int:
    """Whole seconds between two ISO 8601 times.

    Args:
        start: the earlier.
        end: the later.

    Returns:
        The seconds, never negative.
    """
    return max(0, int((moment(end) - moment(start)).total_seconds()))
