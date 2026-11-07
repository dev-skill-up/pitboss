"""The ``DISK`` line of ``next`` and the ``clean the disk`` suggestion (pitboss#288).

A full disk stopped the queue three times in a day: every Bash call failed, and
``next`` went on suggesting workers. So ``next`` and ``slots next`` read the free
space of the workspace's volume (the injected ``disk.Reader``, keyword:
disk-injected) and say it: a ``DISK`` line always, a warning on it from 85 % used,
a first suggestion ``clean the disk`` from 90 % used, and no worker suggestion
below 1 GiB free. The cleaning it names is the auto-approved ``clean-container``
(the owner's ruling of 2026-11-07), never a per-path ``rm``.
"""

import dataclasses
import pathlib
from typing import Callable, Iterable, Sequence

from . import disk, machine
from .markers import Marker

SOON_PERCENT = 85.0
CLEAN_PERCENT = 90.0
STARVED_FREE = disk.BYTES_IN_GIBIBYTE
LARGEST = 5
CLEAN_WORKTREES = "uvx pitboss clean-worktrees --no-dry-run"
CLEAN_CONTAINER = "uvx pitboss clean-container --no-dry-run"
HEADER = "clean the disk"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """The use of the volume the work happens on.

    Attributes:
        place: the path that was read (the workspace).
        usage: its file system's use.
    """

    place: pathlib.Path
    usage: disk.Usage

    @property
    def percent(self) -> float:
        """How much of the volume is used, as ``df`` counts it.

        Returns:
            The percent.
        """
        return machine.percent_used(self.usage)

    @property
    def starved(self) -> bool:
        """Whether less than 1 GiB is free: no worker can run.

        Returns:
            True under 1 GiB free.
        """
        return self.usage.free < STARVED_FREE

    @property
    def crowded(self) -> bool:
        """Whether the clean suggestion is due: 90 % used or more, or starved.

        Returns:
            True when the first suggestion is to clean the disk.
        """
        return self.percent >= CLEAN_PERCENT or self.starved


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Big:
    """One of the largest entries under the scratch directories.

    Attributes:
        path: the entry.
        size: the bytes it holds.
    """

    path: pathlib.Path
    size: int


def read(reader: disk.Reader, place: pathlib.Path) -> Reading | None:
    """Read the use of the volume of a path.

    Args:
        reader: reads the use of a path's file system.
        place: the path (the workspace).

    Returns:
        The reading, or None when the path is not there.
    """
    found = reader(place)
    return Reading(place=place, usage=found) if found else None


def line(each: Reading) -> str:
    """The ``DISK`` line.

    Args:
        each: the reading.

    Returns:
        The free space and the percent used; from 85 % used it says to clean
        before the disk is full, and from 90 % that the first suggestion does.
    """
    text = (
        f"{Marker.DISK.text} {each.place}: {disk.size_text(each.usage.free)} free of"
        f" {disk.size_text(each.usage.total)} ({each.percent:.1f}% used)"
    )
    if each.crowded:
        return f"{text}: the first suggestion is to {HEADER}"
    if each.percent >= SOON_PERCENT:
        return f"{text}: clean before it fills: {CLEAN_CONTAINER}"
    return text


def largest(
    children: Callable[[pathlib.Path], Sequence[pathlib.Path]],
    size: Callable[[pathlib.Path], int],
    roots: Iterable[pathlib.Path],
) -> Sequence[Big]:
    """The five largest entries directly under some directories.

    Args:
        children: lists a directory.
        size: the bytes a path holds.
        roots: the scratch directories (``[clean] scratch``).

    Returns:
        Up to five, the largest first.
    """
    every = [
        Big(path=each, size=size(each)) for root in roots for each in children(root)
    ]
    return sorted(every, key=lambda one: one.size, reverse=True)[:LARGEST]


def suggestion(each: Reading, big: Sequence[Big]) -> Sequence[str]:
    """The lines of the ``clean the disk`` suggestion.

    Args:
        each: the reading, of a crowded volume.
        big: the largest scratch entries.

    Returns:
        The commands in the order to run them, then the five largest entries.
    """
    lines = [
        f"The volume of {each.place} is {each.percent:.1f}% used,"
        f" {disk.size_text(each.usage.free)} free: clean before any worker starts.",
        f"1. {CLEAN_WORKTREES}",
        f"2. {CLEAN_CONTAINER}",
        f"3. the {LARGEST} largest entries under the scratch directories:",
    ]
    named = [f"   {disk.size_text(one.size)} {one.path}" for one in big]
    return [*lines, *(named or ["   none found"])]


def starved_line(each: Reading) -> str:
    """The line that replaces the worker suggestions under 1 GiB free.

    Args:
        each: the reading.

    Returns:
        The ``SUGGESTION`` line that says no worker starts.
    """
    return (
        f"{Marker.SUGGESTION.text}: none: {disk.size_text(each.usage.free)} free"
        f" under {disk.size_text(STARVED_FREE)}: no worker starts until the disk"
        " is cleaned"
    )
