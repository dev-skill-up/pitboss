"""The tickets a PR says it fixes."""

from typing import AbstractSet, Sequence

from . import fixnames, ledger, pullfacts


def fixed_tickets(pull: pullfacts.PullFacts) -> AbstractSet[str]:
    """The tickets a PR's body says it fixes or closes.

    A PR that closes several tickets (an Opus ruling allows it, keyword: fold,
    pitboss#171) has a ``Closes`` line for each beyond the first; each is a
    ticket this PR fixes, so ``pitboss next`` never starts a second PR for it.

    Args:
        pull: the PR.

    Returns:
        Each ``Fixes #N``, ``Closes #N`` or ``owner/repo#N`` form of them in
        its body, in full.
    """
    return frozenset(
        ledger.reference(found, pull.repo)
        for found in fixnames.FIXES.findall(pull.pull.body)
    )


first_fixed = fixnames.first_fixed


def head_fixing(ticket: str, facts: Sequence[pullfacts.PullFacts]) -> str:
    """The head of the first open PR that fixes a ticket.

    Args:
        ticket: the ticket in full.
        facts: the open PRs.

    Returns:
        The head commit, or empty when no PR fixes the ticket.
    """
    heads = [each.pull.head.sha for each in facts if ticket in fixed_tickets(each)]
    return heads[0] if heads else ""


def of_pull(pull: pullfacts.PullFacts) -> str:
    """The ticket a PR says it fixes.

    Args:
        pull: the PR.

    Returns:
        The first ticket its body fixes, as ``owner/name#number``, or "".
    """
    return first_fixed(pull.pull.body or "", pull.repo)
