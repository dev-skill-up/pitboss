"""Tests for UNREADABLE REVIEW: a review comment not in the form (pitboss#106)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import reviews, shapes, unreadableform
from . import test_plan_revision, test_roundlimit

HEAD = test_plan_revision.HEAD
URL = "https://github.com/owner/project/pull/3#issuecomment-6529013244"
REVIEW = test_roundlimit.REVIEW
IN_FORM = f"## Review\nReviewed: {HEAD}\nPlan: approved\nVerdict: approved\n"
OFF_FORM = "Plan: approved\nVerdict: changes needed\nExecution: wrong\n"
WRONG = "is not in the review form: the first line is 'Plan: approved', not '## Review'"
MARK = "UNREADABLE REVIEW"


def comment(body: str, author: str = "MEMBER") -> shapes.Comment:
    """An issue comment.

    Args:
        body: its text.
        author: its author's association.

    Returns:
        The comment.
    """
    return shapes.Comment(body=body, author_association=author, created_at="1", url=URL)


def found(
    body: str, slug: str = "o/x", author: str = "MEMBER"
) -> Sequence[unreadableform.UnreadableReview]:
    """What the sweep finds unreadable among one comment.

    Args:
        body: the comment's text.
        slug: the repository.
        author: the comment's author association.

    Returns:
        The findings.
    """
    _, form = reviews.rules(REVIEW, slug)
    posted = [comment(body, author)]
    return unreadableform.find(posted, REVIEW.trusted, form, reviews.line_pattern)


def marked(body: str) -> Sequence[str]:
    """The UNREADABLE REVIEW lines of a sweep of a world with one comment.

    Args:
        body: the text of PR 3's only comment.

    Returns:
        The lines.
    """
    swept = test_plan_revision.outputs(comment(body))[0]
    return [line for line in swept.splitlines() if MARK in line]


class TestSweepPrintsIt(unittest.TestCase):
    """The sweep line, end to end."""

    def test_a_comment_not_in_the_form_is_named(self) -> None:
        """Plan, Verdict and Execution lines under another first line are named."""
        lines = marked(OFF_FORM)
        assert_that(len(lines), equal_to(1))
        assert_that(lines[0], contains_string(f"{MARK} owner/project#3: {URL} {WRONG}"))

    def test_a_review_in_form_is_not(self) -> None:
        """A review in the repository's form prints no such line."""
        assert_that(marked(IN_FORM), equal_to([]))

    def test_a_comment_with_no_grade_line_is_not(self) -> None:
        """A comment with no Verdict, Plan or Execution line is no review."""
        assert_that(marked("LGTM\n"), equal_to([]))


class TestFinding(unittest.TestCase):
    """Which comments are named, and what is said of the first line."""

    def test_each_grade_line_starts_one(self) -> None:
        """A line starting Verdict:, Plan: or Execution: does, at any place."""
        for line in ("Verdict: approved", "Plan: approved", "Execution: approved"):
            assert_that(len(found(f"Looks fine\n\n{line}\n")), equal_to(1), line)

    def test_the_finding_names_the_comment_and_the_first_line(self) -> None:
        """The URL and what is wrong with the first line are in the finding."""
        finding = found("Reviewed\nVerdict: approved\n")[0]
        problem = "the first line is 'Reviewed', not '## Review'"
        assert_that((finding.url, finding.problem), equal_to((URL, problem)))

    def test_an_empty_first_line_is_said(self) -> None:
        """A comment that opens with a blank line says so."""
        problem = "the first line is empty, not '## Review'"
        assert_that(found("\nVerdict: approved\n")[0].problem, equal_to(problem))

    def test_a_long_first_line_is_cut(self) -> None:
        """The finding stays one short line."""
        problem = found("x" * 500 + "\nVerdict: approved\n")[0].problem
        assert_that(len(problem) < 200, equal_to(True))
        assert_that(problem, contains_string("..."))

    def test_the_form_first_line_is_a_review(self) -> None:
        """A comment whose first line is the form's is not named, read or not."""
        broken = f"## Review\nReviewed: {HEAD}\nPlan: approved\n"
        assert_that(found(IN_FORM), equal_to([]))
        assert_that(found(broken), equal_to([]))

    def test_a_stranger_is_not_trusted(self) -> None:
        """Only a trusted author's comment counts."""
        assert_that(found(OFF_FORM, author="NONE"), equal_to([]))

    def test_a_grade_word_inside_a_line_is_not(self) -> None:
        """The line must start with the word, not hold it."""
        assert_that(found("See the Verdict: approved above\n"), equal_to([]))

    def test_a_gated_repository_uses_the_gated_form(self) -> None:
        """The first line a gated repository expects is the gated form's."""
        gated = found(IN_FORM, slug="owner/gated")
        assert_that(gated[0].problem, contains_string("'## Gated review'"))
        assert_that(
            found(IN_FORM.replace("## R", "## Gated r"), "owner/gated"), equal_to([])
        )

    def test_the_form_has_no_lines(self) -> None:
        """A form with no lines expects nothing of a first line."""
        empty = dataclasses.replace(REVIEW.form, lines=())
        posted = [comment(OFF_FORM)]
        named = unreadableform.find(posted, REVIEW.trusted, empty, reviews.line_pattern)
        assert_that(named, equal_to([]))
