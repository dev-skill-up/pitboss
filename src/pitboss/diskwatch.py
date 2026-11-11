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
from typing import Iterable, NamedTuple, Sequence

from . import disk, machine
from .markers import Marker

SOON_PERCENT = 85.0
CLEAN_PERCENT = 90.0
STARVED_FREE = disk.BYTES_IN_GIBIBYTE
NOX_FREE = 5 * disk.BYTES_IN_GIBIBYTE
LARGEST = 5
CLEAN_LOOK = "uvx pitboss clean-container"
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
    def free_text(self) -> str:
        """The free space, spelled.

        Returns:
            The size, as ``disk.size_text`` spells it.
        """
        return disk.size_text(self.usage.free)

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


class Big(NamedTuple):
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


def starved(each: Reading | None) -> bool:
    """Whether a reading has under 1 GiB free.

    Args:
        each: the reading, None when unread.

    Returns:
        True when no worker may be suggested.
    """
    return each is not None and each.starved


def crowded(each: Reading | None) -> bool:
    """Whether a reading is due the ``clean the disk`` suggestion.

    Args:
        each: the reading, None when unread.

    Returns:
        True from 90 % used or under 1 GiB free.
    """
    return each is not None and each.crowded


def line(each: Reading) -> str:
    """The ``DISK`` line.

    Args:
        each: the reading.

    Returns:
        The free space and the percent used; from 85 % used it says to clean
        before the disk is full, and from 90 % that the first suggestion does.
    """
    text = (
        f"{Marker.DISK.text} {each.place}: {each.free_text} free of"
        f" {disk.size_text(each.usage.total)} ({each.percent:.1f}% used)"
    )
    if each.crowded:
        return f"{text}: the first suggestion is to {HEADER}"
    if each.percent >= SOON_PERCENT:
        return f"{text}: clean before it fills: {CLEAN_CONTAINER}"
    return text


NOT_RUN = (
    "nox result: NOT RUN, no session ran (skills, lint, mypy, tests-3.13 not run);"
    " no green result is recorded, so `pitboss push` refuses this tree (keyword:"
    " nox-tree, pitboss#471)"
)


def nox_refusal(each: Reading | None) -> Sequence[str]:
    """The lines that stop ``pitboss nox`` on a volume with little free space.

    A worker fills the disk inside one round (each ``pitboss nox`` makes an
    environment of gigabytes per worktree, pitboss#346), so the command reads
    the volume it writes to before it starts a session.

    Args:
        each: the reading of the working directory's volume, None when unread.

    Returns:
        No line when the volume is unread or has at least 5 GiB free; else the
        ``DISK`` line, the same ``line`` that ``next`` prints, the sentence
        with the auto-approved cleaning that the command stops for, and the
        result line ``NOT_RUN`` (keyword: nox-tree, pitboss#471).
    """
    if each is None or each.usage.free >= NOX_FREE:
        return []
    return [
        line(each),
        f"pitboss nox starts no session under {disk.size_text(NOX_FREE)} free:"
        f" run {CLEAN_CONTAINER}",
        NOT_RUN,
    ]


def largest(files: machine.Filesystem, roots: Iterable[pathlib.Path]) -> Sequence[Big]:
    """The five largest entries directly under some directories.

    Args:
        files: the file system.
        roots: the scratch directories (``[clean] scratch``).

    Returns:
        Up to five, the largest first.
    """
    every = [
        Big(each, files.inspect(each).size) for r in roots for each in files.children(r)
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
        f" {each.free_text} free: clean before any worker starts.",
        f"1. {CLEAN_LOOK}",
        f"2. {CLEAN_CONTAINER}",
        f"3. the {LARGEST} largest entries under the scratch directories:",
    ]
    named = [f"   {disk.size_text(one.size)} {one.path}" for one in big]
    return [*lines, *(named or ["   none found"])]


def opening(each: Reading | None, big: Sequence[Big], total: int) -> Sequence[str]:
    """The lines that come before the worker suggestions.

    Args:
        each: the reading, None when unread.
        big: the largest scratch entries.
        total: how many suggestions are printed.

    Returns:
        Under 1 GiB free, the line that says no worker starts; on a crowded
        volume, the first suggestion ``clean the disk``.
    """
    if each is None:
        return []
    marker = Marker.SUGGESTION.text
    said = []
    if each.starved:
        said.append(
            f"{marker}: none: {each.free_text} free under"
            f" {disk.size_text(STARVED_FREE)}: no worker starts until the disk is"
            " cleaned"
        )
    if each.crowded:
        said.append(f"{marker} 1 of {total}: {HEADER}: {each.place}")
        said.extend(suggestion(each, big))
        said.append("--- end of suggestion 1 ---")
    return said
