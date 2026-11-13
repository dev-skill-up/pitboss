"""How much one command asks to be read (keyword: one-path).

``onepath`` makes it from the mode of the command line, and ``readworld`` reads the
items named, every open pull request for the sweep, and the open pull requests of
the branches ``push --mechanical`` pushes (keyword: mechanical-fix).
"""

import dataclasses
from typing import Sequence

from . import listed, pushdraft
from .running import Run


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Extent:
    """How much a command asks to be read.

    Attributes:
        named: the items examined whatever the walk reaches (the item the
            command names).
        every_pull: whether every open pull request is examined (the sweep).
        pushing: whether the open pull requests of the branches a ``git push``
            pushes are named too (``push --mechanical``, keyword: mechanical-fix).
        pushed: the arguments of that push, which name its branches.
    """

    named: Sequence[str]
    every_pull: bool
    pushing: bool
    pushed: Sequence[str]


def pushed(run: Run, extent: Extent, rows: Sequence[listed.Listed]) -> Sequence[str]:
    """The open pull requests of the branches a push names, from the listing.

    Args:
        run: the runner git reads the current branch through.
        extent: the extent, which says whether a push names its branches.
        rows: every open pull request, as listed.

    Returns:
        Their references; none when no push is named.
    """
    if not extent.pushing:
        return []
    current = pushdraft.current_branch(run)
    branches = pushdraft.branches(extent.pushed, current)
    return [each.reference for each in rows if each.branch in branches]


def naming(items: Sequence[str]) -> Extent:
    """The extent of a command that names items.

    Args:
        items: the items, ``owner/name#number`` each (none for the walk alone).

    Returns:
        The extent.
    """
    return Extent(named=items, every_pull=False, pushing=False, pushed=())


EVERY_PULL = Extent(named=(), every_pull=True, pushing=False, pushed=())


def pushing(arguments: Sequence[str]) -> Extent:
    """The extent of ``push --mechanical``: the pull requests of its branches.

    Args:
        arguments: the push's arguments.

    Returns:
        The extent.
    """
    return Extent(named=(), every_pull=False, pushing=True, pushed=arguments)
