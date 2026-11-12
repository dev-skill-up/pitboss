"""What a push says about the body of the PR it moves (keyword: evidence-stale).

(Pitboss#444, cases 11 and 27.) The fix round of bats PR 650 moved the head and
left the ``pitboss-expand`` blocks at the old one, and a regex edit of the body of
PR 469 dropped its ``## Execution`` section. After a push the command says to
expand again; before one it refuses a body with no Execution once the branch has
changes. ``lint`` and ``plan-check`` refuse the same bodies.
"""

import subprocess
from typing import Sequence

from . import bodyrules, evidence, ghapi
from .running import Run

STALE = "EVIDENCE STALE: re-run uvx pitboss expand"


def _pulls(
    github: ghapi.GitHub, slug: str | None, branch: str
) -> Sequence[dict[str, object]]:
    # the open PRs of the branch; none when it is not known or cannot be read
    if slug is None or not branch:
        return []
    found = ghapi.branch_pulls(github, slug, branch)
    if not isinstance(found, list):
        return []
    return [each for each in found if isinstance(each, dict)]


def stale_line(github: ghapi.GitHub, slug: str | None, branch: str) -> str:
    """The line to print after a push that moved the head of the branch.

    Args:
        github: the API.
        slug: the repository's ``owner/name``, or None when it is not known.
        branch: the pushed branch; empty when it is not known.

    Returns:
        ``STALE`` when the branch has an open PR whose body has an Evidence
        section with a block ``expand`` produced; else empty (also when the PR
        cannot be read).
    """
    bodies = [f"{each.get('body') or ''}" for each in _pulls(github, slug, branch)]
    return STALE if any(evidence.has_produced(each) for each in bodies) else ""


def missing_execution(
    run: Run, github: ghapi.GitHub, slug: str | None, branch: str
) -> Sequence[str]:
    """The refusals of a push whose PR body lost its ``## Execution`` section.

    Args:
        run: the runner of read-only commands, run in the worktree.
        github: the API.
        slug: the repository's ``owner/name``, or None when it is not known.
        branch: the pushed branch; empty when it is not known.

    Returns:
        A finding for each open PR of the branch with no Execution heading when
        the branch changes a file against the PR's base; none otherwise.
    """
    found: list[str] = []
    for each in _pulls(github, slug, branch):
        if _changes(run, _base_of(each)):
            found.extend(bodyrules.section_findings(f"{each.get('body') or ''}"))
    return found


def _base_of(pull: dict[str, object]) -> str:
    # the branch the PR merges into
    given = pull.get("base")
    named = given.get("ref") if isinstance(given, dict) else None
    return f"{named or 'main'}"


def _changes(run: Run, base: str) -> bool:
    # whether the worktree's head changes a file against the base
    try:
        names = run(["git", "diff", "--name-only", f"origin/{base}...HEAD"]).stdout
    except subprocess.CalledProcessError:
        return False
    return bool(str(names).strip())
