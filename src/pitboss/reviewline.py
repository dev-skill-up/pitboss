"""The sweep's UNREADABLE REVIEW lines (keyword: unreadable-review)."""

from typing import Sequence

from . import pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The lines for the comments of a PR that grade a review not in the form.

    Args:
        pull: the PR.

    Returns:
        One line for each such comment.
    """
    reference = pulls.reference(pull)
    return [
        f"{Marker.UNREADABLE_REVIEW.text} {reference}: {each.url} is not in the"
        f" review form: {each.problem}"
        for each in pull.unreadable_reviews
    ]
