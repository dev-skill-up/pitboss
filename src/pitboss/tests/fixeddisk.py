"""The disk of a test world: a fixed figure, never the host's (pitboss#134)."""

import pathlib

from .. import disk

GIBIBYTE = 2**30


def fixed_usage(path: pathlib.Path) -> disk.Usage:
    """The use of every disk of a world: 100 GiB, half of it free.

    Args:
        path: the path, whose disk is not read.

    Returns:
        The same figures at every call.
    """
    return disk.Usage(100 * GIBIBYTE, 50 * GIBIBYTE, 50 * GIBIBYTE)
