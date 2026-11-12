"""Two open PRs on one ticket (B23, keyword: duplicate-pr).

A session restart does not stop the agents the old session had running: the old
session's worker opened a second PR on a ticket the new session's worker already
had (2026-11-11 14:30Z, one worker over the cap). Two open PRs that fix or are
branched for one ticket are named in a ``DUPLICATE PR`` line with the step.
"""

from typing import AbstractSet, Mapping, Sequence

from . import actions, pullnames, pulls

PREFIX = "DUPLICATE PR"
STEP = "close the newer as a duplicate"


def _tickets(
    facts: Sequence[pulls.PullFacts],
) -> Mapping[str, Sequence[pulls.PullFacts]]:
    by_ticket: dict[str, list[pulls.PullFacts]] = {}
    for each in facts:
        names = pullnames.names(
            each.pull.title, each.pull.body, each.pull.head.branch, each.repo
        )
        for ticket in sorted(names):
            by_ticket.setdefault(ticket, []).append(each)
    return _doubled(by_ticket)


def lines(facts: Sequence[pulls.PullFacts]) -> Sequence[str]:
    """The ``DUPLICATE PR`` lines of the open PRs.

    Args:
        facts: the open PRs that were read.

    Returns:
        A line for each ticket that two or more PRs work on, naming the PRs
        oldest first and the step; none when no ticket has two.
    """
    return [_line(ticket, found) for ticket, found in _tickets(facts).items()]


def newer(facts: Sequence[pulls.PullFacts]) -> AbstractSet[str]:
    """The PRs that are a duplicate: not the oldest of the PRs on a ticket.

    Args:
        facts: the open PRs that were read.

    Returns:
        Their references (``owner/name#number``).
    """
    return {
        pulls.reference(each)
        for found in _tickets(facts).values()
        for each in found[1:]
    }


def _doubled(
    by_ticket: Mapping[str, Sequence[pulls.PullFacts]],
) -> Mapping[str, Sequence[pulls.PullFacts]]:
    return {
        ticket: sorted(found, key=lambda each: each.pull.created_at)
        for ticket, found in by_ticket.items()
        if len({pulls.reference(each) for each in found}) > 1
    }


def _line(ticket: str, found: Sequence[pulls.PullFacts]) -> str:
    named = " and ".join(pulls.reference(each) for each in found)
    return f"{PREFIX}: {named} work ticket {ticket}; step: {STEP}"


def standing_of(
    facts: pulls.PullFacts, every: Sequence[pulls.PullFacts]
) -> actions.Standing:
    """The standing of a PR besides its step.

    Args:
        facts: the PR.
        every: every open PR that was read.

    Returns:
        ``DUPLICATE`` for a second PR on a ticket, else ``PLAIN``.
    """
    if pulls.reference(facts) in newer(every):
        return actions.Standing.DUPLICATE
    return actions.Standing.PLAIN
