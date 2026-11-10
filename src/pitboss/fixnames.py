"""The ``Fixes`` lines of a PR body, read from the text alone (pitboss#443)."""

import re

from . import config, ledger

FIXES = re.compile(
    r"\b(?:Fixes|Closes)\s+((?:[\w.-]+/)?[\w.-]*#\d+)(?!\w)", flags=re.IGNORECASE
)


def first_fixed(body: str, repo: config.Repo) -> str:
    """The ticket the first ``Fixes`` line of a PR body names.

    Args:
        body: the PR's body.
        repo: the PR's repository, the owner of a bare ``#N``.

    Returns:
        The ticket in full, or empty when the body has no ``Fixes``.
    """
    found = FIXES.search(body)
    return ledger.reference(found.group(1), repo) if found else ""
