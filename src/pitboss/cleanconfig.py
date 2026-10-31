"""The ``[clean]`` table: what ``clean-container`` may look at and what it must keep."""

import dataclasses
import enum
import pathlib
from typing import Mapping, Sequence

LIVE_MARKER = ".pitboss-live"
DEFAULT_MIN_FREE_GIB = 5.0
DEFAULT_TMP_ROOTS = (pathlib.Path("/tmp"),)
DEFAULT_TMP_PATTERNS = ("tmp????????", "tmp.??????????", "pytest-of-*", "pip-*")
DEFAULT_TMP_HOURS = 24.0
DEFAULT_PRESSURE_PERCENT = 90.0
DEFAULT_PRESSURE_TMP_HOURS = 1.0


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
        tmp_roots: directories whose test tempdirs a sweep removes by age.
        tmp_patterns: the names (shell patterns) of those tempdirs.
        tmp_hours: how long a tempdir is untouched before a sweep removes it.
        pressure_percent: the disk use, in percent, from which a sweep cleans
            aggressively (keyword: auto-clean).
        pressure_tmp_hours: ``tmp_hours`` under that pressure.
        caches: package caches (beyond the built-in ones in the home
            directory) that regenerate; removed only under that pressure.
    """

    scratch: Sequence[pathlib.Path]
    live: Sequence[pathlib.Path]
    min_free_gib: float
    worktrees: Worktrees = Worktrees.AUTO
    tmp_roots: Sequence[pathlib.Path] = DEFAULT_TMP_ROOTS
    tmp_patterns: Sequence[str] = DEFAULT_TMP_PATTERNS
    tmp_hours: float = DEFAULT_TMP_HOURS
    pressure_percent: float = DEFAULT_PRESSURE_PERCENT
    pressure_tmp_hours: float = DEFAULT_PRESSURE_TMP_HOURS
    caches: Sequence[pathlib.Path] = ()


def absolute(key: str, path: pathlib.Path) -> None:
    """Refuse a path that could name more than was meant.

    Args:
        key: the setting.
        path: the path.

    Raises:
        ValueError: when it is relative (it would follow the working directory)
            or, other than in ``live``, the root of the file system.
    """
    if not path.is_absolute():
        raise ValueError(f"[clean] {key} must be absolute paths, not {str(path)!r}")
    if key != "live" and path == pathlib.Path(path.anchor):
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
    defaults = {"tmp_roots": DEFAULT_TMP_ROOTS}
    lists = {}
    for key in ("scratch", "live", "tmp_roots", "caches"):
        found = table.get(key, list(defaults.get(key, [])))
        if not isinstance(found, list):
            raise ValueError(f"[clean] {key} must be a list of paths, not {found!r}")
        lists[key] = tuple(pathlib.Path(str(item)) for item in found)
        for each in lists[key]:
            absolute(key, each)
    return lists


def _patterns(table: Mapping[str, object]) -> Sequence[str]:
    found = table.get("tmp_patterns", list(DEFAULT_TMP_PATTERNS))
    if not isinstance(found, list) or not all(isinstance(one, str) for one in found):
        raise ValueError(f"[clean] tmp_patterns must be a list of names, not {found!r}")
    if any("/" in one or not one for one in found):
        raise ValueError(f"[clean] tmp_patterns must be names without /, not {found!r}")
    return tuple(found)


def _hours(table: Mapping[str, object], key: str, default: float) -> float:
    hours = float(str(table.get(key, default)))
    if hours < 0:
        raise ValueError(f"[clean] {key} must not be negative, not {hours}")
    return hours


def _percent(table: Mapping[str, object]) -> float:
    key = "pressure_percent"
    percent = float(str(table.get(key, DEFAULT_PRESSURE_PERCENT)))
    if not 0 < percent <= 100:
        raise ValueError(
            f"[clean] {key} must be above 0 and at most 100, not {percent}"
        )
    return percent


def from_document(document: Mapping[str, object]) -> Clean:
    """Read the table.

    Args:
        document: the parsed configuration.

    Returns:
        The settings, empty when the table is absent.

    Raises:
        ValueError: when a list is not a list of absolute paths (none is the
            file system's root, bar ``live``), a threshold or an age is
            negative, the pressure is not in (0, 100], a pattern is not a name
            or ``worktrees`` is neither ``auto`` nor ``list``.
    """
    table = document.get("clean", {})
    if not isinstance(table, dict):
        raise ValueError(f"[clean] must be a table, not {table!r}")
    lists = _lists(table)
    base = Clean(
        scratch=lists["scratch"],
        live=lists["live"],
        min_free_gib=_free(table),
        worktrees=_worktrees(table),
    )
    return _with_auto_clean(base, table, lists)


def _with_auto_clean(
    base: Clean,
    table: Mapping[str, object],
    lists: Mapping[str, Sequence[pathlib.Path]],
) -> Clean:
    return dataclasses.replace(
        base,
        tmp_roots=lists["tmp_roots"],
        tmp_patterns=_patterns(table),
        tmp_hours=_hours(table, "tmp_hours", DEFAULT_TMP_HOURS),
        pressure_percent=_percent(table),
        pressure_tmp_hours=_hours(
            table, "pressure_tmp_hours", DEFAULT_PRESSURE_TMP_HOURS
        ),
        caches=lists["caches"],
    )
