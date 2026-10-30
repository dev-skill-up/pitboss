"""Runs of ``clean-container`` in a test world, and what they print."""

import pathlib
from typing import Sequence

from . import cleanworld, world


def clean(here: world.World, *arguments: str) -> world.Result:
    """Run ``clean-container`` with no marker file.

    Args:
        here: the world.
        *arguments: more arguments.

    Returns:
        What it did.
    """
    return world.again(here, "clean-container", *cleanworld.NO_MARKER, *arguments)


def listed(here: world.World, *arguments: str) -> Sequence[str]:
    """The paths a run of ``clean-container`` removes, or would.

    Args:
        here: the world.
        *arguments: more arguments.

    Returns:
        The paths of its ``REMOVED PATH`` lines.
    """
    return cleanworld.lines_of(clean(here, *arguments).out, "REMOVED PATH")


def names(paths: Sequence[str]) -> Sequence[str]:
    """The last part of each path.

    Args:
        paths: the paths.

    Returns:
        The names, sorted.
    """
    return sorted(pathlib.Path(path).name for path in paths)
