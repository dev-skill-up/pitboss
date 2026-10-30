"""Free space: how much is left, and how it is said."""

import dataclasses
import pathlib
import shutil
from typing import Callable, Iterable, NamedTuple, Sequence

BYTES_IN_GIBIBYTE = 2**30
BYTES_IN_MEBIBYTE = 2**20


class Usage(NamedTuple):
    """What ``shutil.disk_usage`` answers.

    Attributes:
        total: the size of the filesystem.
        used: the bytes used.
        free: the bytes free.
    """

    total: int
    used: int
    free: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Low:
    """A filesystem with little free space.

    Attributes:
        path: a configured path on it.
        free: the bytes free.
    """

    path: pathlib.Path
    free: int


def free_space(path: pathlib.Path) -> int:
    """The bytes free on the filesystem of a path.

    Args:
        path: a path on it.

    Returns:
        The bytes.
    """
    return shutil.disk_usage(path).free


def low_space(
    paths: Iterable[pathlib.Path],
    minimum_gib: float,
    usage: Callable[[pathlib.Path], int] = free_space,
) -> Sequence[Low]:
    """The filesystems of some paths that have less than a minimum free.

    Args:
        paths: the paths; one that is not there is left out.
        minimum_gib: the minimum, in GiB; 0 is never low.
        usage: reads the free bytes of a path.

    Returns:
        One entry for each filesystem, named by its first path.
    """
    seen = set()
    found = []
    for each in paths:
        if not each.exists() or each.stat().st_dev in seen:
            continue
        seen.add(each.stat().st_dev)
        free = usage(each)
        if free < minimum_gib * BYTES_IN_GIBIBYTE:
            found.append(Low(path=each, free=free))
    return found


def size_text(size: int) -> str:
    """Spell a size.

    Args:
        size: bytes.

    Returns:
        ``1.2 GiB`` from a GiB up, else ``3.4 MiB``.
    """
    if size >= BYTES_IN_GIBIBYTE:
        return f"{size / BYTES_IN_GIBIBYTE:.1f} GiB"
    return f"{size / BYTES_IN_MEBIBYTE:.1f} MiB"
