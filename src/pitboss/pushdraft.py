"""A push to the branch of a draft PR is free of the hold (keyword: push-draft).

(Pitboss#355.) The runner-pressure hold covers pushes to non-draft PRs and says
pushes to drafts are free, but ``pitboss push`` decided from its ``--draft`` flag
alone, so a worker that left the flag out was held on a PR that GitHub says is a
draft. The push now reads the draft state of the open PR of each branch it
pushes. A branch with no open PR, a PR that is not a draft, a branch that cannot
be told, or a read that fails is held as before.
"""

import json
import subprocess
import urllib.parse
from typing import Sequence

from . import ghapi
from .running import Run

SAYING = "the open PR of {branch} is a draft: a push to a draft is never held"
_HEADS = "refs/heads/"


def branches(arguments: Sequence[str], current: str) -> Sequence[str]:
    """The branches a ``git push`` with these arguments pushes.

    Args:
        arguments: the arguments after ``push``; options are left out, the
            first of the rest is the remote and the others are refspecs.
        current: the current branch, empty when it is none (a detached head).

    Returns:
        The destination branch of each refspec (``HEAD`` and no refspec mean the
        current branch); none when a refspec names no branch.
    """
    named = [each for each in arguments if not each.startswith("-")]
    refspecs = named[1:] or ["HEAD"]
    found = []
    for each in refspecs:
        target = each.lstrip("+").split(":")[-1]
        branch = current if target == "HEAD" else target.removeprefix(_HEADS)
        if not branch:
            return []
        found.append(branch)
    return found


def current_branch(run: Run) -> str:
    """The branch the working directory is on.

    Args:
        run: the runner of read-only commands.

    Returns:
        The branch's name; empty for a detached head or when git fails.
    """
    try:
        shown = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    except subprocess.CalledProcessError:
        return ""
    return "" if shown == "HEAD" else shown


def drafts(github: ghapi.GitHub, slug: str, branch: str) -> bool:
    """Whether a branch has an open PR and every such PR is a draft.

    Args:
        github: the API.
        slug: the repository's ``owner/name``, which owns the branch.
        branch: the branch's name.

    Returns:
        True when GitHub lists an open PR from the branch and all are drafts;
        False for none, a PR that is ready, or a read that failed.
    """
    owner = slug.split("/")[0]
    head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
    try:
        body = ghapi.get(github, f"repos/{slug}/pulls?head={head}&state=open")
        found = json.loads(body)
    except (subprocess.CalledProcessError, ValueError):
        return False
    if not isinstance(found, list) or not found:
        return False
    return all(isinstance(each, dict) and each.get("draft") is True for each in found)


def all_drafts(
    github: ghapi.GitHub, slug: str, wanted: Sequence[str]
) -> Sequence[str] | None:
    """The branches of a push when every one has an open draft PR.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        wanted: the branches the push pushes.

    Returns:
        The branches, or None when there is none or one is not a draft's.
    """
    if not wanted or not all(drafts(github, slug, each) for each in wanted):
        return None
    return wanted
