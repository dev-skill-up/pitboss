"""The ``DISK PRESSURE`` lines of a sweep: little free space, what could be freed."""

import datetime
from typing import Sequence

from . import dead, deadscan, disk
from .markers import Marker

NAMED = 5


def warning(each: disk.Low, minimum: float) -> str:
    """The line for one filesystem.

    Args:
        each: the filesystem.
        minimum: the minimum free space, in GiB.

    Returns:
        The line.
    """
    return (
        f"{Marker.DISK_PRESSURE.text} {each.path}: {disk.size_text(each.free)} free,"
        f" under {minimum:g} GiB: clean-container removes the dead paths"
    )


def largest(found: Sequence[dead.Candidate]) -> Sequence[str]:
    """Name the largest safe dead paths.

    Args:
        found: the dead paths, largest first.

    Returns:
        An indented line for each of the first few safe ones, or one saying
        that there is none.
    """
    named = [
        f"  {disk.size_text(each.size)} {each.path} ({each.reason})"
        for each in dead.safe(found)[:NAMED]
    ]
    return named or ["  no dead path found"]


def lines(look: dead.Look, now: datetime.datetime) -> Sequence[str]:
    """Warn when a filesystem the cleaning covers is nearly full.

    Nothing is scanned while there is room.

    Args:
        look: what to look at and keep.
        now: the time now.

    Returns:
        A line for each low filesystem, then the largest safe dead paths.
    """
    minimum = look.clean.min_free_gib
    paths = [look.settings.project.workspace, *look.clean.scratch]
    crowded = disk.low_space(paths, minimum)
    if not crowded:
        return []
    found = deadscan.scan(look, now.timestamp())
    return [
        *(warning(each, minimum) for each in crowded),
        *largest(found.candidates),
    ]
