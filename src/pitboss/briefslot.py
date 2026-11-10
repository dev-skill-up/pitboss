"""The first line of every brief: the ticket or PR and the kind (keyword: slots-watch).

``pitboss slots watch`` reads it from the first record of an agent's transcript,
so a row of the ledger is exact and nothing is guessed from prose (pitboss#415).
A brief substituted by hand keeps the line.
"""

from .briefkind import REVIEWS, Kind


def line(kind: Kind, reference: str) -> str:
    """The marker line of a brief.

    Args:
        kind: the kind of brief.
        reference: the PR, or the ticket of a new PR, as ``owner/name#N``.

    Returns:
        ``PITBOSS-SLOT: <owner/repo#N> <start|fix|review|ruling>``.
    """
    if kind in REVIEWS:
        word = "review"
    elif kind is Kind.RULING:
        word = "ruling"
    else:
        word = "start" if kind is Kind.NEW_PR else "fix"
    return f"PITBOSS-SLOT: {reference} {word}"
