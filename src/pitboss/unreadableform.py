"""The comments that grade a review but are not in its form (unreadable-review)."""

import dataclasses
import re
from typing import AbstractSet, Callable, Sequence

from . import config, sessionurl, shapes

PatternOf = Callable[[str, config.ReviewForm], re.Pattern[str]]

_GRADE_LINE = re.compile(r"^\s*(?:Verdict|Plan|Execution):", re.MULTILINE)
_SHOWN = 80


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class UnreadableReview:
    """A comment that grades a review but is not in the review form.

    Attributes:
        url: the comment's address.
        problem: what is wrong with its first line.
    """

    url: str
    problem: str


def first_line_problem(
    body: str, form: config.ReviewForm, pattern_of: PatternOf
) -> str:
    """What is wrong with a comment's first line.

    Args:
        body: the comment.
        form: the form reviews take.
        pattern_of: makes the pattern a line template must match whole.

    Returns:
        The problem, or the empty string when the line is the form's.
    """
    lines = sessionurl.strip(body).splitlines()
    first = lines[0].rstrip() if lines else ""
    wanted = form.lines[0] if form.lines else ""
    if not wanted or pattern_of(wanted, form).fullmatch(first):
        return ""
    if not first:
        return f"the first line is empty, not {wanted!r}"
    shown = first if len(first) <= _SHOWN else first[:_SHOWN] + "..."
    return f"the first line is {shown!r}, not {wanted!r}"


def _grades(body: str) -> bool:
    return bool(_GRADE_LINE.search(sessionurl.strip(body)))


def find(
    posted: Sequence[shapes.Comment],
    trusted: AbstractSet[str],
    form: config.ReviewForm,
    pattern_of: PatternOf,
) -> Sequence[UnreadableReview]:
    """Find the trusted comments that grade a review in no form we read.

    A comment with a line starting ``Verdict:``, ``Plan:`` or ``Execution:``
    whose first line is not the repository's review first line is no review to
    the sweep; it is named so that no PR reads as unreviewed when it is not
    (keyword: unreadable-review, dev-skill-up/pitboss#106).

    Args:
        posted: the PR's issue comments.
        trusted: the author associations whose reviews count.
        form: the form reviews take in the PR's repository.
        pattern_of: makes the pattern a line template must match whole.

    Returns:
        One finding for each such comment, oldest first.
    """
    graded = [
        item
        for item in posted
        if item.author_association in trusted and _grades(item.body)
    ]
    problems = [
        (item, first_line_problem(item.body, form, pattern_of)) for item in graded
    ]
    return [
        UnreadableReview(url=item.url, problem=problem)
        for item, problem in problems
        if problem
    ]
