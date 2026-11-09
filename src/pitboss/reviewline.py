"""The sweep's UNREADABLE REVIEW and EXECUTION REVIEW EARLY lines.

(Keywords: unreadable-review, execution-before-green.)
"""

from typing import Sequence

from . import earlyfound, earlyreview, pulls
from .markers import Marker


def _early(reference: str, each: earlyfound.Premature) -> str:
    return (
        f"{Marker.EXECUTION_REVIEW_EARLY.text}: {reference} reviewed at"
        f" {each.when}, CI completed {each.ci_done or 'not yet'}; one Execution"
        f" review is due (review {earlyreview.comment_id(each.url)} of"
        f" {each.sha} does not count: {each.unfinished})"
    )


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The lines for the comments of a PR that grade a review that does not count.

    An Execution review written before the run of its head finished does not
    count (pitboss#202): after green the step is the one ``slots next`` gives.

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
        *(_early(reference, each) for each in pull.unreadable.premature),
    ]
