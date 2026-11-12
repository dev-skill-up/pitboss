"""The grade lines each kind of review must have (keyword: grade-missing).

quire#1110: an Execution review came back with no ``Execution:`` line at all and
the sweep went on offering the review. The brief of each kind names the lines, the
words and ``--review-kind``, and ``lint review`` refuses a comment without a line its
kind needs, naming the line and the words (the same constants the form and the sweep
read, ``gradeline``).
"""

import argparse
import enum
from typing import Mapping, Protocol, Sequence

from gather.commands import add_argument

from . import gradeline


class Review(enum.Enum):
    """The kinds of review, by the word ``--review-kind`` takes.

    Attributes:
        FULL: the Plan and the Execution in one review.
        PLAN: the Plan alone.
        EXECUTION: the Execution of a head whose Plan is approved.
        RESOLUTION: a merge of the base into an approved head.
        FIX_ROUND: the fixes of the last review's findings.
        RELOCK: a relock PR.
    """

    FULL = "full"
    PLAN = "plan"
    EXECUTION = "execution"
    RESOLUTION = "resolution"
    FIX_ROUND = "fix-round"
    RELOCK = "relock"


# the lines of each kind: a review of the Plan alone grades the Plan; every other
# review grades the Plan (fixed after an approval) and the Execution
BOTH = (gradeline.PLAN_PREFIX, gradeline.EXECUTION_PREFIX)
REQUIRED: Mapping[str, Sequence[str]] = {
    each.value: (gradeline.PLAN_PREFIX,) if each is Review.PLAN else BOTH
    for each in Review
}
ARGUMENT = add_argument(
    "--review-kind",
    choices=tuple(REQUIRED),
    default=Review.FULL.value,
    help="review: the kind of review the comment is (the brief names it); a"
    " review lacks no grade line its kind needs",
)
MISSING = (
    "{name}: the review has no `{line}` line (review kind {kind}); write `{line}"
    " {approved}` or `{line} {changes}` as a line of its own, the verdict word"
    " first (grade-missing)"
)


class Worded(Protocol):
    """A review form: ``config.ReviewForm`` is one."""

    @property
    def approved(self) -> str:
        """Returns the form's word for an approval."""

    @property
    def changes_needed(self) -> str:
        """Returns the form's word that asks for changes."""


class Reviewed(Protocol):
    """A review to check: ``forms.Subject`` is one."""

    @property
    def name(self) -> str:
        """Returns what to call it in a finding."""

    @property
    def body(self) -> str:
        """Returns its text."""


def findings(
    args: argparse.Namespace, subject: Reviewed, form: Worded
) -> Sequence[str]:
    """The grade lines the review's kind needs that it does not have.

    Args:
        args: the parsed arguments of ``lint review``; ``kind`` is the kind.
        subject: the review.
        form: the form the review takes.

    Returns:
        One finding for each missing line, naming it and the accepted words;
        a line that starts as a grade and grades nothing is ``review-grade``'s.
    """
    return [
        MISSING.format(
            name=subject.name,
            line=prefix.rstrip(),
            kind=args.review_kind,
            approved=form.approved,
            changes=form.changes_needed,
        )
        for prefix in REQUIRED[args.review_kind]
        if not gradeline.present(subject.body, prefix)
    ]
