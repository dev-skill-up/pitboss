"""What is found of Execution reviews written before green (pitboss#202).

(Keyword: execution-before-green.) The reading is ``earlyreview``'s, which sits
above ``pulls``; ``pulls`` is given it as ``Source.early``, and keeps the finding.
"""

import dataclasses
from typing import Callable, Sequence

from . import config, shapes


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Premature:
    """An Execution review that was written before the run of its head finished.

    Attributes:
        url: the comment's address.
        when: when it was written (ISO 8601).
        sha: the head it reviewed (possibly abbreviated).
        unfinished: what was not finished (or not green) when it was written.
        ci_done: when the last check of the reviewed head completed, empty
            when a check had not completed or the head had none.
    """

    url: str
    when: str
    sha: str
    unfinished: str
    ci_done: str = ""


def newer(found: Sequence[Premature], counted: str) -> Sequence[Premature]:
    """Keep the early reviews written after the newest counted review.

    One written before it decides nothing: the counted review's standing stands.

    Args:
        found: the early reviews.
        counted: when the newest counted review was written, empty when none.

    Returns:
        The early reviews written later than that.
    """
    return [each for each in found if each.when > counted]


Split = Callable[
    [config.Repo, shapes.Pull, Sequence[shapes.Comment]],
    tuple[Sequence[shapes.Comment], Sequence[Premature]],
]


def keep_all(
    repo: config.Repo, pull: shapes.Pull, comments: Sequence[shapes.Comment]
) -> tuple[Sequence[shapes.Comment], Sequence[Premature]]:
    """Leave every comment in: the reading that finds no review too early.

    Args:
        repo: the PR's repository.
        pull: the PR.
        comments: its comments.

    Returns:
        The comments, and no finding.
    """
    return comments, []
