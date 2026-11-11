"""One walk of a path: how big, how new, and what is in it that must not go.

A path that ``clean-container`` may remove is walked once, whole and without
following a link (keyword: clean-container, ``rules.md``, "Checkouts and disk"):
its size, the newest change in it, a live marker anywhere in it, every git
checkout in it at any depth, every mount point in it and every directory that
could not be read. What a path holds that cannot be seen is a reason to keep it.
"""

import dataclasses
import itertools
import os
import pathlib
import stat
from typing import AbstractSet, Callable, Iterable, Mapping, Sequence

GIT = ".git"
BLOCK = 512
BARE_FILES = frozenset({"HEAD"})
BARE_DIRECTORIES = frozenset({"objects", "refs"})

LIVE_MARKER = ".pitboss-live"
Inspector = Callable[[pathlib.Path], "Survey"]
Entries = tuple[Sequence[str], Sequence[str]]
Statuses = Mapping[str, os.stat_result | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Survey:
    """What a path holds.

    Attributes:
        size: the bytes it holds on disk (a link counts as itself).
        newest: the newest change, in seconds since the epoch (``.git`` apart:
            fetching changes it).
        marked: whether anything in it is named ``.pitboss-live``.
        marked_at: the time the newest such marker was written, or 0 when there
            is none or it is not known.
        repositories: the directories that hold a ``.git``, at any depth.
        bare: the directories that are a bare repository.
        mounts: the mount points in it, or the path itself when it is one;
            none is entered.
        unreadable: what could not be listed or looked at.
    """

    size: int = 0
    newest: float = 0.0
    marked: bool = False
    marked_at: float = 0.0
    repositories: Sequence[pathlib.Path] = ()
    bare: Sequence[pathlib.Path] = ()
    mounts: Sequence[pathlib.Path] = ()
    unreadable: Sequence[pathlib.Path] = ()


def merge(parts: Sequence[Survey]) -> Survey:
    """Put what was found in the parts of a path together.

    Args:
        parts: the surveys of its parts.

    Returns:
        The survey of the whole.
    """
    return Survey(
        size=sum(each.size for each in parts),
        newest=max((each.newest for each in parts), default=0.0),
        marked=any(each.marked for each in parts),
        marked_at=max((each.marked_at for each in parts), default=0.0),
        repositories=tuple(itertools.chain(*(each.repositories for each in parts))),
        bare=tuple(itertools.chain(*(each.bare for each in parts))),
        mounts=tuple(itertools.chain(*(each.mounts for each in parts))),
        unreadable=tuple(itertools.chain(*(each.unreadable for each in parts))),
    )


def listing(path: pathlib.Path) -> Entries:
    """List a directory: its subdirectories, then everything else (links too).

    Args:
        path: the directory.

    Returns:
        The names of the subdirectories and of the other entries; a link to a
        directory is the second, as it is not entered.
    """
    with os.scandir(path) as scanned:
        entries = list(scanned)
    names = {each.name for each in entries if each.is_dir(follow_symlinks=False)}
    return sorted(names), sorted(
        each.name for each in entries if each.name not in names
    )


def status(path: pathlib.Path) -> os.stat_result | None:
    """Look at one entry, without following it.

    Args:
        path: the entry.

    Returns:
        Its status, or None when it is gone or cannot be looked at.
    """
    try:
        return path.lstat()
    except OSError:
        return None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ground:
    """What a walk of one path needs to know.

    Attributes:
        top: the walked path.
        real: the walked path with its links resolved.
        device: the device it is on (a directory on another is a mount point).
        mounts: the mount points of the machine.
        lister: lists a directory.
    """

    top: pathlib.Path
    real: pathlib.Path
    device: int
    mounts: AbstractSet[pathlib.Path]
    lister: Callable[[pathlib.Path], Entries]


Seen = tuple[pathlib.Path, os.stat_result | None]


def sized(seen: Iterable[Seen]) -> Survey:
    """The size and what is unreadable among some entries.

    Args:
        seen: each entry and its status.

    Returns:
        The survey of them.
    """
    kept = list(seen)
    return Survey(
        size=sum(one.st_blocks * BLOCK for _, one in kept if one),
        unreadable=tuple(path for path, one in kept if one is None),
    )


def dated(seen: Iterable[Seen]) -> Survey:
    """The newest change among some entries (``.git`` itself does not count).

    Args:
        seen: each entry and its status.

    Returns:
        The survey of them.
    """
    times = [one.st_mtime for path, one in seen if one and path.name != GIT]
    return Survey(newest=max(times, default=0.0))


def crosses(ground: Ground, found: os.stat_result, place: pathlib.Path) -> bool:
    """Whether a directory is a mount point.

    Args:
        ground: what the walk knows.
        found: the directory's status.
        place: where the mount table would name it.

    Returns:
        True when it is on another device, or is named by the mount table (a
        bind mount on the same device is).
    """
    on_another = found.st_dev != ground.device
    return stat.S_ISDIR(found.st_mode) and (on_another or place in ground.mounts)


def _mount(ground: Ground, here: pathlib.Path, one: str, found: os.stat_result) -> bool:
    # the place the mount table would name is built only when a mount lies below
    place = ground.real
    if ground.mounts:
        place = ground.real / here.relative_to(ground.top) / one
    return crosses(ground, found, place)


def _statuses(here: pathlib.Path, entries: Iterable[str]) -> Statuses:
    # a status is read by the joined text: no path is built for an entry
    prefix = str(here) + os.sep
    seen: dict[str, os.stat_result | None] = {}
    for each in entries:
        try:
            seen[each] = os.lstat(prefix + each)
        except OSError:
            seen[each] = None
    return seen


def _held(here: pathlib.Path, seen: Statuses, inside: bool) -> Survey:
    # what a directory is: a checkout, a bare repository, a marker, and its size
    marker = seen.get(LIVE_MARKER)
    present = set(seen)
    times = [
        one.st_mtime for each, one in seen.items() if one and each != GIT and not inside
    ]
    return Survey(
        size=sum(one.st_blocks * BLOCK for one in seen.values() if one),
        newest=max(times, default=0.0),
        marked=LIVE_MARKER in present and not inside,
        marked_at=marker.st_mtime if marker and not inside else 0.0,
        repositories=(here,) if GIT in present and not inside else (),
        bare=(here,) if BARE_FILES | BARE_DIRECTORIES <= present and not inside else (),
        unreadable=tuple(here / each for each, one in seen.items() if one is None),
    )


def _mounted(
    ground: Ground, here: pathlib.Path, folders: Sequence[str], seen: Statuses
) -> AbstractSet[str]:
    return {
        each
        for each in folders
        if (one := seen[each]) is not None and _mount(ground, here, each, one)
    }


def _below(
    here: pathlib.Path,
    folders: Sequence[str],
    mounted: AbstractSet[str],
    inside: bool,
) -> Sequence[tuple[pathlib.Path, bool]]:
    return [
        (here / each, inside or each == GIT) for each in folders if each not in mounted
    ]


def visit(
    ground: Ground, here: pathlib.Path, inside: bool
) -> tuple[Survey, Sequence[tuple[pathlib.Path, bool]]]:
    """Look at one directory of the walk (keyword: walk-speed, pitboss#453).

    The walk is Python's own work for every entry of a tree, so it builds no path
    it does not need: only a directory to enter is made a path.

    Args:
        ground: what the walk knows.
        here: the directory.
        inside: whether it is in a ``.git`` (a repository's own files).

    Returns:
        What it holds, and its subdirectories to walk (not the mount points)
        with whether each is in a ``.git``.
    """
    try:
        folders, others = ground.lister(here)
    except OSError:
        return Survey(unreadable=(here,)), ()
    seen = _statuses(here, (*folders, *others))
    mounted = _mounted(ground, here, folders, seen)
    found = merge(
        [
            _held(here, seen, inside),
            Survey(mounts=tuple(here / each for each in folders if each in mounted)),
        ]
    )
    return found, _below(here, folders, mounted, inside)


def descend(ground: Ground) -> Sequence[Survey]:
    """Look at every directory under the walked path, the path itself included.

    Args:
        ground: what the walk knows.

    Returns:
        The survey of each directory.
    """
    found = []
    pending = [(ground.top, False)]
    while pending:
        held, below = visit(ground, *pending.pop())
        found.append(held)
        pending.extend(below)
    return found


def walk(
    path: pathlib.Path,
    mounts: AbstractSet[pathlib.Path],
    lister: Callable[[pathlib.Path], Entries] = listing,
) -> Survey:
    """Look at a path, whole.

    A link is measured as itself, never followed; a mount point is not
    entered; a path that is gone is size 0 and unreadable.

    Args:
        path: a file or a directory.
        mounts: the mount points of the machine (``mounts.current``).
        lister: lists a directory.

    Returns:
        What it holds.
    """
    top = status(path)
    first = merge([sized([(path, top)]), dated([(path, top)])])
    if top is None or not stat.S_ISDIR(top.st_mode):
        return first
    real = path.resolve()
    if os.path.ismount(path) or real in mounts:
        return merge([first, Survey(mounts=(path,))])
    below = frozenset(each for each in mounts if each.is_relative_to(real))
    ground = Ground(top=path, real=real, device=top.st_dev, mounts=below, lister=lister)
    return merge([first, *descend(ground)])
