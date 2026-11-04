"""The tickets a PR says it fixes."""

import re
from typing import AbstractSet

from . import config, ledger, pulls

_FIXES = re.compile(
    r"\b(?:Fixes|Closes)\s+((?:[\w.-]+/)?[\w.-]*#\d+)(?!\w)", re.IGNORECASE
)


def fixed_tickets(pull: pulls.PullFacts) -> AbstractSet[str]:
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
        ledger.reference(found, pull.repo) for found in _FIXES.findall(pull.pull.body)
    )


def first_fixed(body: str, repo: config.Repo) -> str:
    """The ticket the first ``Fixes`` line of a PR body names.

    Args:
        body: the PR's body.
        repo: the PR's repository, the owner of a bare ``#N``.

    Returns:
        The ticket in full, or empty when the body has no ``Fixes``.
    """
    found = _FIXES.search(body)
    return ledger.reference(found.group(1), repo) if found else ""
