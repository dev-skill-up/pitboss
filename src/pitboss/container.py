"""Files written in a container after it started, found by a marker file.

A cloud container's image has one file of its own at the root (Claude Code
on the web writes ``/container_info.json`` when the container starts); a
regular file next to it and much newer than it was written by the session.
"""

import dataclasses
import pathlib
import stat
from typing import Sequence

DEFAULT_MARKER = "/container_info.json"
DEFAULT_ROOT = "/"
DEFAULT_HOURS = 1.0


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Found:
    """A regular file newer than the cutoff.

    Attributes:
        path: the file.
        size: its size, in bytes.
    """

    path: pathlib.Path
    size: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Watch:
    """Where a session's own files in the root are looked for.

    Attributes:
        marker: the file the container started with; absent, there are none.
        root: the directory.
        hours: how long after the marker a file must be written.
    """

    marker: pathlib.Path
    root: pathlib.Path
    hours: float


WATCH = Watch(
    marker=pathlib.Path(DEFAULT_MARKER),
    root=pathlib.Path(DEFAULT_ROOT),
    hours=DEFAULT_HOURS,
)


def cutoff(marker: pathlib.Path, hours: float) -> float:
    """The time after which a file is the session's.

    Args:
        marker: the file the container started with.
        hours: how long after the marker a file must be written.

    Returns:
        The time, in seconds since the epoch.
    """
    return marker.stat().st_mtime + hours * 3600


def regular_since(path: pathlib.Path, after: float) -> Found | None:
    """Look at one directory entry.

    Args:
        path: the entry.
        after: the time, in seconds since the epoch.

    Returns:
        The file, or None when it is not a regular file modified after the
        time (or is gone).
    """
    try:
        status = path.lstat()
    except FileNotFoundError:  # pragma: no cover
        # Removed between the listing and now.
        return None
    if stat.S_ISREG(status.st_mode) and status.st_mtime > after:
        return Found(path=path, size=status.st_size)
    return None


def newer_files(root: pathlib.Path, after: float) -> Sequence[Found]:
    """The regular files directly in a directory modified after a time.

    Subdirectories are not searched; symbolic links, directories and
    anything else that is not a regular file are left alone.

    Args:
        root: the directory.
        after: the time, in seconds since the epoch.

    Returns:
        The files, sorted.
    """
    looked = (regular_since(path, after) for path in root.iterdir())
    return sorted(
        (each for each in looked if each is not None), key=lambda each: each.path
    )
