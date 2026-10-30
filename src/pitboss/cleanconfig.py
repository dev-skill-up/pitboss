"""The ``[clean]`` table: what ``clean-container`` may look at and what it must keep."""

import dataclasses
import enum
import pathlib
from typing import Mapping, Sequence

LIVE_MARKER = ".pitboss-live"
DEFAULT_MIN_FREE_GIB = 5.0


class Worktrees(enum.Enum):
    """What a sweep does with the worktrees whose work is finished.

    Attributes:
        AUTO: remove each that passes the safety test, and say which it kept.
        LIST: only list them.
    """

    AUTO = enum.auto()
    LIST = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Clean:
    """What ``clean-container`` looks at and keeps.

    Attributes:
        scratch: directories whose entries are removed when nothing in them
            was touched in the idle hours and nothing marks them live.
        live: paths never removed (shared caches, toolchain homes, the
            persistent checkout); a directory holding a file named
            ``.pitboss-live`` is live too.
        min_free_gib: free space, in GiB, under which a sweep warns; 0 never warns.
        worktrees: ``auto`` (a sweep removes the finished worktrees that pass the
            safety test and says which it kept) or ``list`` (it only lists them).
    """

    scratch: Sequence[pathlib.Path]
    live: Sequence[pathlib.Path]
    min_free_gib: float
    worktrees: Worktrees = Worktrees.AUTO


def absolute(key: str, path: pathlib.Path) -> None:
    """Refuse a path that could name more than was meant.

    Args:
        key: the setting.
        path: the path.

    Raises:
        ValueError: when it is relative (it would follow the working directory)
            or, in ``scratch``, the root of the file system.
    """
    if not path.is_absolute():
        raise ValueError(f"[clean] {key} must be absolute paths, not {str(path)!r}")
    if key == "scratch" and path == pathlib.Path(path.anchor):
        raise ValueError(f"[clean] {key} must not be the root of the file system")


def _worktrees(table: Mapping[str, object]) -> Worktrees:
    found = table.get("worktrees", "auto")
    try:
        return Worktrees[str(found).upper()]
    except KeyError:
        raise ValueError(
            f'[clean] worktrees must be "auto" or "list", not {found!r}'
        ) from None


def _free(table: Mapping[str, object]) -> float:
    free = float(str(table.get("min_free_gib", DEFAULT_MIN_FREE_GIB)))
    if free < 0:
        raise ValueError(f"[clean] min_free_gib must not be negative, not {free}")
    return free


def _lists(table: Mapping[str, object]) -> Mapping[str, Sequence[pathlib.Path]]:
    lists = {}
    for key in ("scratch", "live"):
        found = table.get(key, [])
        if not isinstance(found, list):
            raise ValueError(f"[clean] {key} must be a list of paths, not {found!r}")
        lists[key] = tuple(pathlib.Path(str(item)) for item in found)
        for each in lists[key]:
            absolute(key, each)
    return lists


def from_document(document: Mapping[str, object]) -> Clean:
    """Read the table.

    Args:
        document: the parsed configuration.

    Returns:
        The settings, empty when the table is absent.

    Raises:
        ValueError: when a list is not a list of absolute paths (a scratch
            directory is not the file system's root), the threshold is
            negative or ``worktrees`` is neither ``auto`` nor ``list``.
    """
    table = document.get("clean", {})
    if not isinstance(table, dict):
        raise ValueError(f"[clean] must be a table, not {table!r}")
    lists = _lists(table)
    return Clean(
        scratch=lists["scratch"],
        live=lists["live"],
        min_free_gib=_free(table),
        worktrees=_worktrees(table),
    )
