"""The Plans that reviews approved (keyword: plan-approved, pitboss#296)."""

from typing import Sequence

from . import config, flowstate, reviews, shapes


def digests(
    comments: Sequence[shapes.Comment], review: config.Review, slug: str
) -> Sequence[str]:
    """The Plan digests that reviews approved.

    Args:
        comments: the PR's issue comments.
        review: how reviews are read.
        slug: the PR's repository (``owner/name``), empty when it is not known,
            and then its reviews are read in the ordinary form.

    Returns:
        The digest each regular review that approves the Plan records.
    """
    sources = reviews.Sources(comments=comments, reviews=())
    return flowstate.approved_digests(reviews.recorded(review, slug, sources))
