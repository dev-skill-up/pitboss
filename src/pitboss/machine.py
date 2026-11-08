"""What the automatic cleaning reads from the machine, all of it injected.

The file system, the disk reader, the clock, the user and the home directory are
values of a ``Machine``, so the tests play a fake one (keyword: auto-clean,
pitboss#120; the rule is in ``rules.md``, "Checkouts and disk").
"""

import dataclasses
import datetime
import math
import os
import pathlib
import shutil
from typing import AbstractSet, Callable, Mapping, Sequence

from . import disk, mounts, procs, survey


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Filesystem:
    """What the cleaning asks of the file system.

    Attributes:
        children: lists a directory (sorted; none when it is not there).
        exists: says whether something is at a path (a link counts as itself).
        is_link: says whether a path is a symbolic link.
        owner: says who owns a path (a link is not followed); None when it cannot
            be read, as when it just went.
        inspect: walks a path once: size, newest change, marker, mount points.
        changed: when a path itself last changed (seconds since the epoch, a link
            not followed), without a walk; None when it cannot be read. A
            directory's walk is never older than this.
    """

    children: Callable[[pathlib.Path], Sequence[pathlib.Path]]
    exists: Callable[[pathlib.Path], bool]
    is_link: Callable[[pathlib.Path], bool]
    owner: Callable[[pathlib.Path], int | None]
    inspect: Callable[[pathlib.Path], survey.Survey]
    changed: Callable[[pathlib.Path], float | None]


def _children(directory: pathlib.Path) -> Sequence[pathlib.Path]:
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def _owner(path: pathlib.Path) -> int | None:
    # A path that went between the listing and now has no owner: not mine.
    try:
        return path.lstat().st_uid
    except OSError:
        return None


def _inspect(path: pathlib.Path) -> survey.Survey:
    return survey.walk(path, mounts.current())


def _changed(path: pathlib.Path) -> float | None:
    found = survey.status(path)
    return None if found is None else found.st_mtime


def real() -> Filesystem:
    """The file system of this machine.

    Returns:
        The file system.
    """
    return Filesystem(
        children=_children,
        exists=os.path.lexists,
        is_link=pathlib.Path.is_symlink,
        owner=_owner,
        inspect=_inspect,
        changed=_changed,
    )


def read_usage(path: pathlib.Path) -> disk.Usage | None:
    """Read the use of the file system of a path.

    Args:
        path: a path on it.

    Returns:
        The use, or None when the path is not there.
    """
    try:
        return disk.Usage(*shutil.disk_usage(path))
    except OSError:
        return None


def nobody() -> AbstractSet[pathlib.Path]:
    """The directories no process works in: what a machine of no processes says.

    Returns:
        None.
    """
    return frozenset()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Machine:
    """What the cleaning reads from the machine.

    Attributes:
        fs: the file system.
        usage: reads the use of a path's file system, None when absent.
        now: the time now.
        uid: the user whose tempdirs are removed.
        home: the home directory, where the package caches are.
        working: the directories the command runs in; never removed.
        busy: reads the directories the running processes work in; a tempdir
            that is or holds one is not removed (pitboss#348).
    """

    fs: Filesystem
    usage: disk.Reader
    now: datetime.datetime
    uid: int
    home: pathlib.Path
    working: AbstractSet[pathlib.Path] = frozenset()
    busy: Callable[[], AbstractSet[pathlib.Path]] = nobody


def real_machine(
    env: Mapping[str, str],
    now: datetime.datetime,
    working: AbstractSet[pathlib.Path],
    usage: disk.Reader = read_usage,
) -> Machine:
    """This machine.

    Args:
        env: the environment of the command.
        now: the time now.
        working: the directories the command runs in.
        usage: reads the use of a path's file system.

    Returns:
        The machine: the real file system and disk, the user running.
    """
    return Machine(
        fs=real(),
        usage=usage,
        now=now,
        uid=os.getuid(),
        home=pathlib.Path(env.get("HOME", str(pathlib.Path.home()))),
        working=working,
        busy=procs.in_use,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Crowded:
    """A file system used up to the pressure.

    Attributes:
        place: a configured path on it.
        percent: how much of it is used.
        over: the bytes to free to get under the limit and over the minimum
            free space.
        free: the bytes free.
        short: whether the free bytes are under the minimum (the second rule of
            pressure, pitboss#205), whatever the percent used.
        free_rule: whether the free bytes, not the percent used, set ``over``
            (the file system needs more freed to have the minimum free than to
            get under the limit).
    """

    place: pathlib.Path
    percent: float
    over: int = 0
    free: int = 0
    short: bool = False
    free_rule: bool = False


def percent_used(usage: disk.Usage) -> float:
    """How much of a file system is used, as ``df`` counts it.

    Args:
        usage: its use.

    Returns:
        The percent; 0 for a file system of no size.
    """
    shown = usage.used + usage.free
    return 100 * usage.used / shown if shown else 0.0


def find_crowded(
    machine: Machine,
    places: Sequence[pathlib.Path],
    limit: float,
    minimum_gib: float = 0.0,
) -> Sequence[Crowded]:
    """The file systems used up to the limit or with too little free, each once.

    Args:
        machine: the machine.
        places: the configured paths; one that is not there is left out.
        limit: the percent from which a file system is crowded.
        minimum_gib: the free space, in GiB, under which a file system is
            crowded too; 0 never is (pitboss#205).

    Returns:
        One entry for each, named by its first path.
    """
    seen: set[disk.Usage] = set()
    found = []
    least = math.ceil(minimum_gib * disk.BYTES_IN_GIBIBYTE)
    for each in places:
        usage = machine.usage(each)
        if usage is None or usage in seen:
            continue
        seen.add(usage)
        if percent_used(usage) >= limit or usage.free < least:
            found.append(crowd(each, usage, limit, least))
    return found


def crowd(
    place: pathlib.Path, usage: disk.Usage, limit: float, least: int = 0
) -> Crowded:
    """A file system crowded, with the bytes to free to get out of it.

    Args:
        place: a configured path on it.
        usage: its use.
        limit: the percent it must get under.
        least: the free bytes it must have.

    Returns:
        The entry; it is at least 1 byte over.
    """
    shown = usage.used + usage.free
    short = usage.free < least
    by_percent = math.ceil(usage.used - shown * limit / 100) + 1
    by_free = least - usage.free + 1 if short else 0
    return Crowded(
        place=place,
        percent=percent_used(usage),
        over=max(1, by_percent, by_free),
        free=usage.free,
        short=short,
        free_rule=by_free > by_percent,
    )
