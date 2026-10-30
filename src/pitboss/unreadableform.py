"""The comments that grade a review but are not in its form (unreadable-review)."""

import dataclasses
import re
from typing import AbstractSet, Callable, Sequence

from . import config, sessionurl, shapes

PatternOf = Callable[[str, config.ReviewForm], re.Pattern[str]]
Reader = Callable[[str, config.ReviewForm], tuple[str, shapes.Verdict] | None]

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
        if item.author_association in trusted and _GRADE_LINE.search(item.body)
    ]
    problems = [
        (item, first_line_problem(item.body, form, pattern_of)) for item in graded
    ]
    return [
        UnreadableReview(url=item.url, problem=problem)
        for item, problem in problems
        if problem
    ]


def _attempts(body: str, form: config.ReviewForm) -> bool:
    lines = sessionurl.strip(body).splitlines()
    first = lines[0].lower() if lines else ""
    words = (form.approved.lower(), form.changes_needed.lower())
    return "review" in first and any(word in first for word in words)


def unread(
    posted: Sequence[shapes.Comment],
    trusted: AbstractSet[str],
    rules: tuple[Reader, config.ReviewForm],
    since: str,
) -> str:
    """Find a newer comment that tries to be a review and is not read as one.

    A comment whose first line says review and a verdict, but which is not
    in the form (a reviewer wrote ``re-review``), is ignored, so the older
    review keeps standing; the sweep says so (dev-skill-up/pitboss#20).

    Args:
        posted: the PR's issue comments.
        trusted: the author associations whose reviews count.
        rules: the reader and the form of the PR's repository.
        since: when the newest review that counts was written, or empty.

    Returns:
        When the newest such comment was written, or the empty string.
    """
    read, form = rules
    ignored = (
        item.created_at
        for item in posted
        if item.author_association in trusted
        and read(item.body, form) is None
        and _attempts(item.body, form)
    )
    return max((when for when in ignored if when > since), default="")
