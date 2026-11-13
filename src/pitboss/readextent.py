"""How much one command asks to be read (keyword: one-path).

``onepath`` makes it from the mode of the command line, and ``readworld`` reads the
items named, every open pull request for the sweep, and the open pull requests of
the branches ``push --mechanical`` pushes (keyword: mechanical-fix).
"""

import dataclasses
import subprocess
from typing import Sequence

from . import exempt, ghapi, pushdraft


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


def _remote(github: ghapi.GitHub, arguments: Sequence[str]) -> str:
    # the repository a push goes to (its first word, else origin); empty for none
    remote = next((each for each in arguments if not each.startswith("-")), "origin")
    try:
        url = github.run(["git", "remote", "get-url", remote]).stdout
    except subprocess.CalledProcessError:
        return ""
    return exempt.slug_of(url) or ""


def pushed(github: ghapi.GitHub, extent: Extent) -> Sequence[str]:
    """The open pull requests of the branches a push names, one read for each.

    The search rows have no branch (keyword: org-search), so each branch the push
    names is asked of the repository it is pushed to, one read for each.

    Args:
        github: the API, whose runner git reads the branch and the remote through.
        extent: the extent, which says whether a push names its branches.

    Returns:
        Their references; none when no push is named.
    """
    if not extent.pushing:
        return []
    current = pushdraft.current_branch(github.run)
    branches = pushdraft.branches(extent.pushed, current)
    slug = _remote(github, extent.pushed) if branches else ""
    return [
        f"{slug}#{each['number']}"
        for branch in branches
        if slug
        for each in ghapi.branch_pulls(github, slug, branch)
    ]


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
