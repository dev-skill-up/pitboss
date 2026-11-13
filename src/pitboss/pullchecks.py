"""What an open PR's facts say of its checks, its conflict and its review.

Apart from ``pulls``, the reader, so a module that only judges facts does not sit
on the reader (keyword: one-path).
"""

from . import conflicts, pullref, reviews, steps
from .pullfacts import PullFacts

failed_checks = pullref.failed_checks


def unhealthy(facts: PullFacts) -> bool:
    """Whether the PR has a failed check, a conflict or is a draft.

    Args:
        facts: the PR.

    Returns:
        True when it is any of them.
    """
    return bool(failed_checks(facts)) or conflicted(facts) or facts.pull.draft


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


def at_merge(facts: PullFacts) -> bool:
    """Whether the PR's step is the merge.

    Args:
        facts: the PR.

    Returns:
        True at the merge.
    """
    return steps.step_is(facts.step, {steps.Step.MERGE})
