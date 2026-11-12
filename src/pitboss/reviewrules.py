"""What a review may not say, split or cut piecemeal (pitboss#444 items 4, 6 and 38).

A review never says a change makes or made a passage false (review-phrase, owner
2026-11-08 22:59Z), and gives one verdict for the whole PR (split-verdict, owner
2026-11-10 20:45Z: "Execution approved, Plan changes needed <-- THAT IS NOT
POSSIBLE"), and never asks for a documentation cut a sentence at a time
(piecemeal, owner 2026-11-08 23:47Z: cut the whole section in one pass). The module
reads nothing, as the review text is given.
"""

import re
from typing import Sequence

from . import config, gradeline

PHRASE_CHECK = "review-phrase"
FALSE = re.compile(
    r"\bmak(?:es|ing|e)\s+(?:\w+\s+){0,3}?false\b|\bmade\s+false\b", re.I
)
SAY = (
    "{check}: line {number} says a change makes text false ({text!r}); say what"
    " the text now says instead"
)
PIECEMEAL_CHECK = "review-piecemeal"
PIECE = re.compile(
    r"\b(?:cut|remove|delete|drop|reword|trim)\s+(?:the\s+|this\s+|that\s+|a\s+)?"
    r"(?:\w+\s+){0,2}?(?:sentence|clause|phrase|bullet|line|word)s?\b"
    r"|\bdepends?\s+on\s+(?:a|the)\s+(?:cut|removed|deleted)\s+"
    r"(?:passage|section|sentence|paragraph|line)\b",
    re.I,
)
DOC = re.compile(
    r"\.(?:md|rst)\b|\bREADME\b|\bdocs?\b|\bdocstring\b|\bdocumentation\b", re.I
)
PIECEMEAL = (
    "{check}: line {number} asks for a documentation cut a part at a time ({text!r});"
    " name the whole section and cut it in one pass"
)
GRADE_CHECK = "review-grade"
UNGRADED = (
    "{check}: the line {text!r} grades nothing, so the sweep does not count it;"
    " write `Plan: {approved}` or `Plan: {changes}` (the same for `Execution:`)"
    " with the verdict word first (keyword: grade-spellings, rp#684)"
)


def phrase_findings(review: str) -> Sequence[str]:
    """The lines of a review that say a change makes text false.

    Args:
        review: the review comment.

    Returns:
        A finding for each such line, with its number.
    """
    return [
        SAY.format(check=PHRASE_CHECK, number=number, text=line.strip()[:80])
        for number, line in enumerate(review.splitlines(), 1)
        if FALSE.search(line)
    ]


def piecemeal_findings(review: str) -> Sequence[str]:
    """The lines of a review that ask for a documentation cut a part at a time.

    Args:
        review: the review comment.

    Returns:
        A finding for each line that names a doc and asks to cut, trim or reword
        a sentence, clause, line or the like, or says text depends on a cut
        passage; a line that asks for a whole section to be cut is not one.
    """
    return [
        PIECEMEAL.format(check=PIECEMEAL_CHECK, number=number, text=line.strip()[:80])
        for number, line in enumerate(review.splitlines(), 1)
        if PIECE.search(line) and DOC.search(line)
    ]


def is_split(review: str, form: config.ReviewForm = config.DEFAULT_REVIEW_FORM) -> bool:
    """Whether the Plan and Execution lines of a review grade differently.

    Args:
        review: the review comment.
        form: the form reviews take, whose words the lines are graded by.

    Returns:
        True when one of the two lines approves and the other asks for changes,
        each read as the sweep reads it.
    """
    grades = [
        gradeline.line_approved(review, prefix, form.approved, form.changes_needed)
        for prefix in (gradeline.PLAN_PREFIX, gradeline.EXECUTION_PREFIX)
    ]
    return None not in grades and grades[0] != grades[1]


def grade_findings(
    review: str, form: config.ReviewForm = config.DEFAULT_REVIEW_FORM
) -> Sequence[str]:
    """The Plan and Execution lines of a review that the sweep cannot read.

    Args:
        review: the review comment.
        form: the form reviews take, whose words the lines are graded by.

    Returns:
        A finding for each line that starts as a grade and grades nothing.
    """
    return [
        UNGRADED.format(
            check=GRADE_CHECK,
            text=line,
            approved=form.approved,
            changes=form.changes_needed,
        )
        for line in gradeline.ungraded(review, form.approved, form.changes_needed)
    ]
