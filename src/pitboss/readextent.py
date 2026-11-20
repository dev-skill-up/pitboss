"""How much one command asks to be read (keyword: one-path).

``mode.question_of`` states it (``modequestion.Extent``), and ``readworld`` reads the
items named, every open pull request for the sweep, and the open pull requests of
the branches ``push --mechanical`` pushes (keyword: mechanical-fix).
"""

import subprocess
from typing import Sequence

from . import exempt, ghapi, pushdraft
from .modequestion import Extent


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
