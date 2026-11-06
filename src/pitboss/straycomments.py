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
        unanalysed: the address of the newest trusted Opus ruling comment when
            it has no ``How we got here`` section (keyword: how-we-got-here).
        premature: the Execution reviews written before green, which do not
            count (keyword: execution-before-green).
    """

    newer: str = ""
    graded: Sequence[unreadableform.UnreadableReview] = ()
    unanalysed: Sequence[str] = ()
    premature: Sequence[earlyfound.Premature] = ()
