"""The ``[clean]`` table: what ``clean-container`` may look at and what it must keep."""

import dataclasses
import pathlib
from typing import Mapping, Sequence

LIVE_MARKER = ".pitboss-live"
DEFAULT_MIN_FREE_GIB = 5.0


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
    """

    scratch: Sequence[pathlib.Path]
    live: Sequence[pathlib.Path]
    min_free_gib: float


def from_document(document: Mapping[str, object]) -> Clean:
    """Read the table.

    Args:
        document: the parsed configuration.

    Returns:
        The settings, empty when the table is absent.

    Raises:
        ValueError: when a list is not a list or the threshold is negative.
    """
    table = document.get("clean", {})
    if not isinstance(table, dict):
        raise ValueError(f"[clean] must be a table, not {table!r}")
    lists = {}
    for key in ("scratch", "live"):
        found = table.get(key, [])
        if not isinstance(found, list):
            raise ValueError(f"[clean] {key} must be a list of paths, not {found!r}")
        lists[key] = tuple(pathlib.Path(str(item)) for item in found)
    free = float(table.get("min_free_gib", DEFAULT_MIN_FREE_GIB))
    if free < 0:
        raise ValueError(f"[clean] min_free_gib must not be negative, not {free}")
    return Clean(scratch=lists["scratch"], live=lists["live"], min_free_gib=free)
