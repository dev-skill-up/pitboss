"""A review lacks no grade line its kind needs (keyword: grade-missing, quire#1110).

The Execution review of quire#1110 came back with no ``Execution:`` line and the
sweep went on offering the review. The brief of each kind names the lines, the
words and ``--review-kind``; ``lint review`` refuses the comment without a line its
kind needs; the sweep names a review of an approved Plan that grades no Execution.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import briefgrade, briefkind, gradesrequired
from . import briefmake
from .linting import HEAD, lines, lint, write_text

START = f"## Review\nReviewed: {HEAD}\nVerdict: approved\n"
ACCEPTED = "`Execution: approved` or `Execution: changes needed`"


def checked(body: str, *kind: str) -> tuple[int, Sequence[str]]:
    """Run ``lint review`` on a review of a kind.

    Args:
        body: the review.
        *kind: the review kind word, none for the default.

    Returns:
        The exit status and the lines printed.
    """
    path = write_text("review.md", body)
    ran = lint(
        "review", path, "--head", HEAD, *(["--review-kind", *kind] if kind else [])
    )
    return ran.code, lines(ran)


class TestKinds(unittest.TestCase):
    """The table, the briefs and the lines agree."""

    def test_c23_every_review_kind_has_its_word_and_its_lines(self) -> None:
        """The words cover ``REVIEWS``; the lines are those the brief prints."""
        assert_that(set(briefgrade.KIND_WORDS), equal_to(set(briefkind.REVIEWS)))
        for kind in briefkind.REVIEWS:
            with self.subTest(kind.name):
                required = gradesrequired.REQUIRED[briefgrade.KIND_WORDS[kind]]
                printed = [
                    each.strip().split(":")[0] + ": "
                    for each in briefgrade.grade_lines(kind, "approved", "changes")
                ]
                assert_that(list(required), equal_to(printed))

    def test_c23_each_brief_prints_its_kind_and_the_accepted_words(self) -> None:
        """`--review-kind WORD`, both verdict words and the not-counted warning."""
        for kind in briefkind.REVIEWS:
            with self.subTest(kind.name):
                text = briefmake.text(kind)
                word = briefgrade.KIND_WORDS[kind]
                assert_that(text, contains_string(f"--review-kind {word}"))
                assert_that(text, contains_string("`approved` or `changes needed`"))
                assert_that(text, contains_string("is not counted"))


class TestLint(unittest.TestCase):
    """`lint review --review-kind` names the missing line and the accepted words."""

    def test_c23_a_missing_execution_line_is_named(self) -> None:
        """An Execution review with the fixed Plan line and no Execution line."""
        code, found = checked(f"{START}Plan: approved (fixed)\n", "execution")
        assert_that(code, equal_to(1))
        assert_that(found[0], contains_string("no `Execution:` line"))
        assert_that(found[0], contains_string(ACCEPTED))

    def test_c23_a_missing_plan_line_on_a_combined_review_is_named(self) -> None:
        """A full review with an Execution line and no Plan line."""
        code, found = checked(f"{START}Execution: approved\n", "full")
        assert_that(code, equal_to(1))
        assert_that(found[0], contains_string("no `Plan:` line"))
        assert_that(found[0], contains_string("`Plan: approved` or `Plan: changes"))

    def test_c23_a_prose_line_is_no_grade_line(self) -> None:
        """`Execution looks fine` is prose: the line is missing."""
        code, found = checked(f"{START}Plan: approved\nExecution looks fine.\n", "full")
        assert_that(code, equal_to(1))
        assert_that(found[0], contains_string("no `Execution:` line"))

    def test_c23_the_default_kind_is_a_full_review(self) -> None:
        """No `--review-kind` asks for both lines."""
        code, found = checked(f"{START}Plan: approved\n")
        assert_that(code, equal_to(1))
        assert_that(found[0], contains_string("no `Execution:` line"))

    def test_c23_a_plan_review_needs_only_the_plan_line(self) -> None:
        """Kind plan passes with the Plan line; the others need both."""
        plan = f"{START}Plan: approved\n"
        both = f"{plan}Execution: approved\n"
        assert_that(checked(plan, "plan"), equal_to((0, ["ok"])))
        for kind in gradesrequired.REQUIRED:
            with self.subTest(kind):
                assert_that(checked(both, kind)[1], equal_to(["ok"]))
