"""How long a worker runs, and the live markers older than that (keyword: auto-clean).

A worker's task is bounded, so a ``.pitboss-live`` marker written longer ago than
that belongs to no running worker: it outlived its work (pitboss#194).
"""

import datetime
from typing import Protocol

TASK_HOURS = 6


class Marked(Protocol):
    """What a walk of a path found about its live marker."""

    @property
    def marked(self) -> bool:
        """Whether the path holds a marker.

        Returns:
            True when it does.
        """

    @property
    def marked_at(self) -> float:
        """When the newest marker was written, 0 when not known.

        Returns:
            Seconds since the epoch.
        """


def expiry_of(now: datetime.datetime) -> float:
    """The time before which a ``.pitboss-live`` marker is too old to honor.

    Args:
        now: the time now.

    Returns:
        Seconds since the epoch: now less the worker's task bound.
    """
    return now.timestamp() - TASK_HOURS * 3600


def expired(expiry: float, found: Marked) -> bool:
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
