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

import functools
from typing import Callable, Sequence

from . import blockedby, concurrently, failures, ghapi, headchecks, listed, pulls
from . import shapes, world
from .sharedstep import MAIN, Seen, Shared, at_fix, groups

__all__ = ["Seen", "groups", "closure", "PREFIX"]

PREFIX = "SHARED RED"
Reader = world.PullReader


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


def closure(
    github: ghapi.GitHub,
    pull: pulls.PullFacts,
    others: Callable[[], Sequence[pulls.PullFacts]],
) -> Sequence[Shared]:
    """Read a red PR's closure: the groups its failed checks are in (plan 3.1, 4).

    Args:
        github: the API.
        pull: the PR.
        others: reads the repository's other open PRs, each at the step its
            blockers give it.

    Returns:
        The groups of its repository; none when the PR is at no fix step.
    """
    if not at_fix(pull):
        return []
    red = [each for each in [pull, *others()] if at_fix(each)]
    seen = _of_prs(github, red)
    found = groups([*seen, *_of_main(github, red, seen)])
    return [each for each in found if each.slug == pull.repo.slug]


def _holder(github: ghapi.GitHub, read: Reader, row: listed.Listed) -> pulls.PullFacts:
    # a shared red's other holder, at the step its blockers give it
    return blockedby.at_blockers(github, read(row))


def holders_closure(
    github: ghapi.GitHub,
    read: Reader,
    pull: pulls.PullFacts,
    others: Sequence[listed.Listed],
) -> Sequence[Shared]:
    """Read a red PR's closure from the other open rows of its repository.

    Args:
        github: the API.
        read: reads one pull request (once a run).
        pull: the PR.
        others: the other open rows of its repository.

    Returns:
        The groups of its repository (``closure``).
    """
    holder = functools.partial(_holder, github, read)
    return closure(github, pull, functools.partial(concurrently.each, holder, others))
