"""Why the review follows a ruling's steps: the two comment times (keyword: ruling-reason).

PR 460 was offered ``do the ruling's steps`` after a Plan check at the head was
posted, later than the ruling (pitboss#444, case 24); the line of the review
says the two times so that the orchestrator reads why.
"""

from typing import AbstractSet, Sequence

from . import flowstate, sessionurl, shapes, steps


def times(
    comments: Sequence[shapes.Comment],
    trusted: AbstractSet[str],
    step: steps.Next,
) -> tuple[str, str]:
    """The newest ruling and the newest clean Plan check, for a review of the steps.

    Args:
        comments: the comments of the PR.
        trusted: the author associations whose comments count.
        step: the step the flow gave the PR.

    Returns:
        The two times, or two empty strings when the step is not the review of a
        ruling's steps.
    """
    if step.stage is not steps.Stage.RULING_STEPS:
        return "", ""
    rulings = [
        each.created_at
        for each in comments
        if flowstate.is_ruling(each.body) and each.author_association in trusted
    ]
    checks = [
        each.created_at
        for each in comments
        if steps.PLAN_CHECK_OK in sessionurl.lines(each.body)
    ]
    return max(rulings, default=""), max(checks, default="")


def reason(ruled_at: tuple[str, str]) -> str:
    """The words that say why, empty when there are no times.

    Args:
        ruled_at: what ``times`` gave.

    Returns:
        The words.
    """
    ruling, check = ruled_at
    if not ruling or not check:
        return ""
    return f" (the Plan check of {check} is later than the ruling of {ruling})"
