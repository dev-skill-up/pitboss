"""The line of an Execution review written before green (keyword: execution-before-green).

An Execution review of a head written while the PR was a draft, or while a check
of that head was unfinished, does not count (pitboss#202, quire#1038): the PR's
next step is the review again after green.
"""

from typing import Sequence

from . import earlyreview, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The EXECUTION REVIEWED BEFORE GREEN lines of a PR.

    Args:
        pull: the PR.

    Returns:
        One line for each Execution review that does not count, oldest first.
    """
    return [
        f"{Marker.EXECUTION_REVIEWED_BEFORE_GREEN.text} {pulls.reference(pull)}:"
        f" review {earlyreview.comment_id(each.url)} at {each.sha} does not count;"
        f" {each.unfinished}; the next step is the review again after green"
        for each in pull.premature
    ]
