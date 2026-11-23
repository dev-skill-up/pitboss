"""One ruling for a PR; a further rejection is a worker round (keyword: one-ruling).

Owner, 2026-11-11: one ruling per PR, so a second Opus ruling is never posted
(A6, pitboss#444). ``refusal`` is what ``pitboss ruling post`` asks before it
posts. The module reads nothing, as the comments are given.
"""

from typing import Sequence

from . import flowstate

SECOND = (
    "the PR already has an Opus ruling: a further rejection is a worker round"
    " (pitboss#517), and a PR no round can finish is `pitboss impossible`"
)


def refusal(comments: Sequence[str]) -> str:
    """Say why a ruling may not be posted on a PR.

    Args:
        comments: the texts of the PR's comments.

    Returns:
        The reason when the PR has a ruling; an empty string for a first ruling.
    """
    return SECOND if any(flowstate.is_ruling(each) for each in comments) else ""
