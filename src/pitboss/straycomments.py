"""The comments of a PR that try to be reviews and are not in the form."""

import dataclasses
from typing import Sequence

from . import earlyfound, unreadableform


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class StrayComments:
    """The comments of a PR that try to be reviews and are not in the form.

    Attributes:
        newer: when a newer comment that tries to be a review but is not in
            the form was written (it is ignored), else empty.
        graded: the trusted comments that grade a review but are not in the
            review form.
        premature: the Execution reviews written before green, which do not
            count (keyword: execution-before-green).
        no_execution: the addresses of the reviews of the head that follow an
            approved Plan and have no ``Execution:`` line (keyword: review-unread).
    """

    newer: str
    graded: Sequence[unreadableform.UnreadableReview]
    premature: Sequence[earlyfound.Premature]
    no_execution: Sequence[str]


# no stray comment
NONE = StrayComments(newer="", graded=(), premature=(), no_execution=())
