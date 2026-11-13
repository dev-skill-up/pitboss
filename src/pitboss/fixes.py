"""The tickets a PR says it fixes."""

from typing import AbstractSet

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
