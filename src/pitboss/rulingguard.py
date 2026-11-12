"""One ruling for a PR; a further rejection goes to the owner (keyword: one-ruling).

Owner, 2026-11-11: after a ruling a further rejection is the owner's, so a second
Opus ruling is never posted on a PR that is not yet paused for him (A6, pitboss#444).
``refusal`` is what ``pitboss ruling post`` asks before it posts. The module reads
nothing: the comments and the labels are given.
"""

from typing import Sequence

from . import flowstate, steps

SECOND = (
    "the PR already has an Opus ruling and is not paused: a further rejection"
    f" goes to the owner, so run `pitboss owner-pause` (label `{steps.PAUSED_LABEL}`)"
    " instead of posting a second ruling"
)


def refusal(comments: Sequence[str], labels: Sequence[str]) -> str:
    """Say why a ruling may not be posted on a PR.

    Args:
        comments: the texts of the PR's comments.
        labels: the PR's labels.

    Returns:
        The reason when the PR has a ruling and is not paused for the owner; an
        empty string otherwise (a first ruling, or a PR the owner decides).
    """
    if steps.PAUSED_LABEL in labels:
        return ""
    return SECOND if any(flowstate.is_ruling(each) for each in comments) else ""
