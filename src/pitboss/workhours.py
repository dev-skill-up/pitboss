"""How long a worker runs, and the live markers older than that (keyword: auto-clean).

A worker's task is bounded, so a ``.pitboss-live`` marker written longer ago than
that belongs to no running worker: it outlived its work (pitboss#194).
"""

import datetime

from . import survey

TASK_HOURS = 6


def expiry_of(now: datetime.datetime) -> float:
    """The time before which a ``.pitboss-live`` marker is too old to honor.

    Args:
        now: the time now.

    Returns:
        Seconds since the epoch: now less the worker's task bound.
    """
    return now.timestamp() - TASK_HOURS * 3600


def expired(expiry: float, found: survey.Survey) -> bool:
    """Whether the newest marker in a path is older than a worker's task.

    Args:
        expiry: the time before which a marker is too old (``expiry_of``); 0
            honors every marker.
        found: what a walk of the path found.

    Returns:
        True when the path holds a marker and none was written since
        ``expiry`` (a marker whose time is not known is honored).
    """
    return found.marked and 0 < found.marked_at < expiry
