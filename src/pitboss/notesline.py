"""The sweep's REVIEW NOTE line (keyword: review-note, pitboss#240)."""

from typing import Sequence

from . import pulls, shapes
from .markers import Marker

SHOWN = 200


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line of an approved PR whose newest review has a note naming a gap.

    Args:
        pull: the PR.

    Returns:
        One line when the newest review that counts approves and its
        ``Notes`` paragraph mentions ``missed``, ``never counted``, ``not
        handled`` or ``only``; else none.
    """
    found = pull.review
    if found is None or found.verdict is not shapes.Verdict.APPROVED or not found.note:
        return []
    shown = found.note if len(found.note) <= SHOWN else found.note[:SHOWN] + "..."
    return [
        f"{Marker.REVIEW_NOTE.text} {pulls.reference(pull)}: the newest review"
        f" approves with a note that names a case: {shown!r}; a note that names a"
        " case of the goal the change does not handle is a finding: read it before"
        " merging, and start a fix round, not a ticket"
    ]
