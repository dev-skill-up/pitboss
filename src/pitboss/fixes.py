"""The tickets a PR says it fixes."""

import re
from typing import AbstractSet

from . import ledger, pulls

_FIXES = re.compile(r"\bFixes\s+((?:[\w.-]+/)?[\w.-]*#\d+)(?!\w)", re.IGNORECASE)


def fixed_tickets(pull: pulls.PullFacts) -> AbstractSet[str]:
    """The tickets a PR's body says it fixes.

    Args:
        pull: the PR.

    Returns:
        Each ``Fixes #N`` or ``Fixes owner/repo#N`` of its body, in full.
    """
    return frozenset(
        ledger.reference(found, pull.repo) for found in _FIXES.findall(pull.pull.body)
    )
