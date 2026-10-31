"""What the automatic cleaning reads from the machine, all of it injected.

The file system, the disk reader, the clock, the user and the home directory are
values of a ``Machine``, so the tests play a fake one (keyword: auto-clean,
pitboss#120; the rule is in ``rules.md``, "Checkouts and disk").
"""

import dataclasses
import datetime
import os
import pathlib
import shutil
from typing import AbstractSet, Callable, Mapping, Sequence

from . import disk, mounts, survey


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Filesystem:
    """What the cleaning asks of the file system.

    Attributes:
        children: lists a directory (sorted; none when it is not there).
        exists: says whether something is at a path (a link counts as itself).
        is_link: says whether a path is a symbolic link.
        owner: says who owns a path (a link is not followed).
        inspect: walks a path once: size, newest change, marker, mount points.
    """

    children: Callable[[pathlib.Path], Sequence[pathlib.Path]]
    exists: Callable[[pathlib.Path], bool]
    is_link: Callable[[pathlib.Path], bool]
    owner: Callable[[pathlib.Path], int]
    inspect: Callable[[pathlib.Path], survey.Survey]


def _children(directory: pathlib.Path) -> Sequence[pathlib.Path]:
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def _owner(path: pathlib.Path) -> int:
    return path.lstat().st_uid


def _inspect(path: pathlib.Path) -> survey.Survey:
    return survey.walk(path, mounts.current())


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
    """

    fs: Filesystem
    usage: Callable[[pathlib.Path], disk.Usage | None]
    now: datetime.datetime
    uid: int
    home: pathlib.Path
    working: AbstractSet[pathlib.Path] = frozenset()


def real_machine(
    env: Mapping[str, str],
    now: datetime.datetime,
    working: AbstractSet[pathlib.Path],
) -> Machine:
    """This machine.

    Args:
        env: the environment of the command.
        now: the time now.
        working: the directories the command runs in.

    Returns:
        The machine: the real file system and disk, the user running.
    """
    return Machine(
        fs=real(),
        usage=read_usage,
        now=now,
        uid=os.getuid(),
        home=pathlib.Path(env.get("HOME", str(pathlib.Path.home()))),
        working=working,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Crowded:
    """A file system used up to the pressure.

    Attributes:
        place: a configured path on it.
        percent: how much of it is used.
    """

    place: pathlib.Path
    percent: float


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
    machine: Machine, places: Sequence[pathlib.Path], limit: float
) -> Sequence[Crowded]:
    """The file systems used up to the limit, each once.

    Args:
        machine: the machine.
        places: the configured paths; one that is not there is left out.
        limit: the percent from which a file system is crowded.

    Returns:
        One entry for each, named by its first path.
    """
    seen: set[disk.Usage] = set()
    found = []
    for each in places:
        usage = machine.usage(each)
        if usage is None or usage in seen:
            continue
        seen.add(usage)
        if percent_used(usage) >= limit:
            found.append(Crowded(place=each, percent=percent_used(usage)))
    return found
