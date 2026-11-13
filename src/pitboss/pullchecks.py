"""What an open PR's facts say of its checks, its conflict and its review.

Apart from ``pulls``, the reader, so a module that only judges facts does not sit
on the reader (keyword: one-path).
"""

from . import conflicts, reviews, steps
from .pullfacts import PullFacts


def conflicted(facts: PullFacts) -> bool:
    """Whether the PR has a merge conflict.

    Args:
        facts: the PR.

    Returns:
        True on a conflict.
    """
    return conflicts.is_dirty(facts.pull)


def approved(facts: PullFacts) -> bool:
    """Whether the head's review approves it, no ruling having voided it.

    Args:
        facts: the PR.

    Returns:
        True when approved (keyword: ruling-voids, pitboss#467).
    """
    counted = (reviews.Standing.APPROVED, reviews.Standing.APPROVED_BEFORE_MERGES)
    return facts.standing in counted and (
        steps.task_of(facts.step) is not steps.Task.RULING_STEPS
    )
