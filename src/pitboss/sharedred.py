"""A check that is red on several PRs from one cause (keyword: shared-red).

Seen on quire: ``canonical-files`` was red on three PRs because a pin was 107
commits stale, and each PR was handled by itself with no pointer to the cause.
A failing check of one name and one first error line on two or more open PRs of
a repository, or on its main and a PR, is one finding: ``SHARED RED`` names the
check, the PRs and the line. The first PR (lowest number) is offered the one
step, to file a single ticket against the cause; the others wait for it, and
no per-PR fix is offered meanwhile. Shapes of "the same cause, many PRs" this
covers a stale pin, a stale lock, a runner outage and a broken main, whenever
the check and its first error line agree; it leaves out causes whose first
error lines differ (the lines are compared whole).
"""

import dataclasses
from typing import Callable, Sequence

from . import failures, ghapi, headchecks, pulls, shapes, steps

PREFIX = "SHARED RED"
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


def stepped(pull: pulls.PullFacts, shared: Sequence[Shared]) -> steps.Move | None:
    """The step a PR has instead of its own fix, while a shared red is open.

    Args:
        pull: the PR.
        shared: the groups of its repository.

    Returns:
        The one ticket step for the lowest-numbered PR of a group, the wait for
        the others; None when the PR is at no fix step or in no group.
    """
    mine = pulls.reference(pull)
    groups_of = [each for each in shared if mine in each.holders]
    if not (_at_fix(pull) and groups_of):
        return None
    first = [each for each in groups_of[0].holders if each != MAIN][0]
    if first == mine:
        return steps.worker(steps.Task.SHARED_RED)
    return steps.Idle(pending=steps.Pending.SHARED_RED)


def _seen(
    github: ghapi.GitHub,
    pull: pulls.PullFacts,
    holder: str,
    checks: Sequence[shapes.CheckRun],
) -> Sequence[Seen]:
    return [
        Seen(
            slug=pull.repo.slug,
            holder=holder,
            check=check.name,
            line=failures.describe(failures.read(github, pull.repo, check)),
        )
        for check in checks
        if check.failed
    ]


def _at_fix(pull: pulls.PullFacts) -> bool:
    return steps.task_of(pull.step) is steps.Task.FIX_CI


def _of_prs(github: ghapi.GitHub, red: Sequence[pulls.PullFacts]) -> Sequence[Seen]:
    found: list[Seen] = []
    for each in red:
        names = {check.id: check.name for check in each.checks}
        for identifier, failure in failures.read_all(github, each).items():
            found.append(
                Seen(
                    slug=each.repo.slug,
                    holder=pulls.reference(each),
                    check=names[identifier],
                    line=failures.describe(failure),
                )
            )
    return found


def _of_main(
    github: ghapi.GitHub, red: Sequence[pulls.PullFacts], seen: Sequence[Seen]
) -> Sequence[Seen]:
    found: list[Seen] = []
    by_base = {(each.repo.slug, each.pull.base): each for each in red}
    for (slug, base), each in by_base.items():
        names = {item.check for item in seen if item.slug == slug}
        runs = headchecks.runs_of(github, each.repo, base)
        found += _seen(github, each, MAIN, [run for run in runs if run.name in names])
    return found


def settle(
    github: ghapi.GitHub, reads: Sequence[pulls.Read]
) -> tuple[Sequence[pulls.Read], Sequence[Shared]]:
    """Replace the fix step of every PR in a shared red, and say the groups.

    Args:
        github: the API.
        reads: every open PR.

    Returns:
        The PRs, those in a group at the ticket step or the wait, and the groups.
    """
    open_pulls = pulls.readable(reads)
    red = [each for each in open_pulls if _at_fix(each)]
    seen = _of_prs(github, red)
    found = groups([*seen, *_of_main(github, red, seen)])
    return [_replaced(each, found) for each in reads], found


def settle_one(
    github: ghapi.GitHub,
    read: pulls.Read,
    others: Callable[[], Sequence[pulls.Read]],
) -> pulls.Read:
    """Settle one PR's shared red, reading the others of its repository only if red.

    The closure of an examined PR (keyword: one-path): a PR at the fix step is
    compared with the same check of the repository's other open PRs and of main.

    Args:
        github: the API.
        read: the PR.
        others: reads the repository's other open PRs, each settled by its
            blockers.

    Returns:
        The PR, at the ticket step or the wait when it is in a group.
    """
    fixing = [each for each in pulls.readable([read]) if _at_fix(each)]
    return settle(github, [read, *(others() if fixing else [])])[0][0]


def _replaced(read: pulls.Read, shared: Sequence[Shared]) -> pulls.Read:
    if isinstance(read, shapes.Unreadable):
        return read
    step = stepped(read, [each for each in shared if each.slug == read.repo.slug])
    return dataclasses.replace(read, step=step) if step else read
