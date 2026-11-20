"""The step a PR in a shared red has, from its closure as read (keyword: shared-red).

``sharedred`` reads the closure (the same failed check on the repository's other
open PRs and on main); ``decide`` gives the PR the step this module says, with no
read of its own (the one-path plan, 6.1: the settlers are rows of ``decide``).
"""

import dataclasses
from typing import Sequence

from . import pullref, steps
from .blockedstep import AtStep

MAIN = "main"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """One failed check of one PR, or of the main branch.

    Attributes:
        slug: the repository, ``owner/name``.
        holder: the PR's ``owner/name#number``, or ``main``.
        check: the check's name.
        line: the first error line read of the failure (see ``failures``).
    """

    slug: str
    holder: str
    check: str
    line: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Shared:
    """A check red on several holders with the same first error line.

    Attributes:
        slug: the repository.
        check: the check's name.
        line: the first error line.
        holders: the PRs (by number) and ``main`` that have it.
    """

    slug: str
    check: str
    line: str
    holders: Sequence[str]


def _number(holder: str) -> int:
    return int(holder.rpartition("#")[2]) if "#" in holder else 0


def groups(seen: Sequence[Seen]) -> Sequence[Shared]:
    """The failures that two or more holders of one repository share.

    Args:
        seen: every failed check of the open PRs and of main.

    Returns:
        One group for each repository, check and error line with at least two
        holders; a failure with no line and no step is never shared.
    """
    found: dict[tuple[str, str, str], list[str]] = {}
    for each in seen:
        if each.line:
            found.setdefault((each.slug, each.check, each.line), []).append(each.holder)
    return [
        Shared(slug=slug, check=check, line=line, holders=sorted(set(who), key=_number))
        for (slug, check, line), who in found.items()
        if len(set(who)) >= 2
    ]


def stepped(pull: AtStep, shared: Sequence[Shared]) -> steps.Move | None:
    """The step a PR has instead of its own fix, while a shared red is open.

    Args:
        pull: the PR.
        shared: the groups of its repository.

    Returns:
        The one ticket step for the lowest-numbered PR of a group, the wait for
        the others; None when the PR is at no fix step or in no group.
    """
    mine = pullref.reference(pull)
    groups_of = [each for each in shared if mine in each.holders]
    if not (at_fix(pull) and groups_of):
        return None
    first = [each for each in groups_of[0].holders if each != MAIN][0]
    if first == mine:
        return steps.worker(steps.Task.SHARED_RED)
    return steps.IDLE


def at_fix(pull: AtStep) -> bool:
    """Whether a PR is at the step that fixes its CI.

    Args:
        pull: the PR.

    Returns:
        True at ``FIX_CI``.
    """
    return steps.task_of(pull.step) is steps.Task.FIX_CI
