"""One ruling for a PR; a further rejection is a worker round (keyword: one-ruling).

Owner, 2026-11-11: one ruling per PR, so a second
Opus ruling is never posted on a PR that is not yet paused for him (A6, pitboss#444).
``refusal`` is what ``pitboss ruling post`` asks before it posts. The module
reads nothing, as the comments and the labels are given.
"""

from typing import Sequence

from . import flowstate, steps

SECOND = (
    "the PR already has an Opus ruling and is not paused: a further rejection"
    " is a worker round (pitboss#517), and a PR no round can finish is `pitboss"
    " impossible`, or `pitboss owner-pause` (label"
    f" `{steps.PAUSED_LABEL}`) when it escalated"
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
