"""The sweep's UNREADABLE REVIEW and EXECUTION REVIEWED BEFORE GREEN lines.

(Keywords: unreadable-review, execution-before-green.)
"""

from typing import Sequence

from . import earlyreview, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The lines for the comments of a PR that grade a review that does not count.

    An Execution review written before the run of its head finished does not
    count (pitboss#202): the PR's next step is the review again after green.

    Args:
        pull: the PR.

    Returns:
        One line for each comment not in the review form, then one for each
        Execution review written before green.
    """
    reference = pulls.reference(pull)
    return [
        *(
            f"{Marker.UNREADABLE_REVIEW.text} {reference}: {each.url} is not in the"
            f" review form: {each.problem}"
            for each in pull.unreadable.graded
        ),
        *(
            f"{Marker.EXECUTION_REVIEWED_BEFORE_GREEN.text} {reference}: review"
            f" {earlyreview.comment_id(each.url)} at {each.sha} does not count;"
            f" {each.unfinished}; the next step is the review again after green"
            for each in pull.unreadable.premature
        ),
    ]
