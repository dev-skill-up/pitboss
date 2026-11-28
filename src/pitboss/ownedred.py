"""A red check that an open p0 ticket names is that ticket's (keyword: owned-red).

quire#1128 was given "fix the CI" for ``e2e (extras)``, red from a test its diff
does not touch; the open p0 ticket quire#1137 names that run and job (pitboss#531).
No worker of the PR can clear such a red, so the PR waits for the ticket, which is
offered in its place (``examine`` puts it in the PR's waits, as ``allowlistmiss``
does for an allowlist line). A ticket that names no run or job of the head owns
nothing; a closed one is not read, so the PR is at the fix of its CI again; and a
ticket the PR itself works on never blocks it (keyword: plan-refusal).
"""

from typing import Sequence

from . import ghapi, headchecks, pullfacts, pullnames, redtickets


def ids(pull: pullfacts.PullFacts) -> Sequence[int]:
    """The run and job ids of the failed checks of a PR's head.

    Args:
        pull: the PR.

    Returns:
        Each id once, none for a check that is no Actions check.
    """
    failed = headchecks.unanswered_of(pull)
    return sorted({each for check in failed for each in (check.run, check.id) if each})


def owners(github: ghapi.GitHub, pull: pullfacts.PullFacts) -> Sequence[str]:
    """The open p0 tickets that name a failed run or job of a PR's head.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        The tickets as ``owner/name#N``, none that the PR itself works on.
    """
    named = ids(pull)
    if not named:
        return []
    mine = pullnames.names(
        pull.pull.title, pull.pull.body, pull.pull.head.branch, pull.repo
    )
    found = redtickets.read_tickets(github, [pull.repo], named)
    return [
        redtickets.name(each)
        for each in found
        if each.cited and redtickets.name(each) not in mine
    ]
