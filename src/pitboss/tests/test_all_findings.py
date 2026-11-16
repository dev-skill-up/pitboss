"""A review lists every finding in one round; the later round checks those (#169)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import brief, missed, shapes
from . import blank, test_brief
from .briefmake import APPROVED, HEAD, PLAN_REVIEWS, pinned, text
from .says import has_all, has_none

FIRST_ROUND = (
    "Round: read the whole PR body, the whole diff and every command of the Plan"
    " against the repository, and list every finding of the stage you grade in"
    " that one review, not the first few."
)
LATER_ROUND = (
    "Round: check only the findings of the earlier review and the findings caused"
    " by the changes made since the head it read."
)
MISSED_EARLIER = "Missed earlier: a review that is not the first round"
DRY_RUN = (
    "in a review of the Plan, try each command of the Plan as a read-only dry run"
    " where it can be tried (it changes nothing in the repository, the PR or the"
    " machine), and report each that cannot run as written as a finding of the"
    " Plan."
)
FIX_ROUND_CLAUSE = (
    f"The diff to read is `git diff {APPROVED}..{HEAD}`. Check that each"
    " finding is fixed as the finding asks, whether the fixes invalidate the"
    " approved Plan, and the CI on the head, and nothing else. You may raise"
    " nothing outside that diff or those findings:"
)
FIX_ROUND_VERDICT = (
    "If every finding is fixed as asked and the fixes do not invalidate the"
    " approved Plan, the verdict is approved, and the PR is mergeable."
)
STAGES = test_brief.FULL_SCOPES
PLAN_STAGES = PLAN_REVIEWS
OUTSIDE_THE_FIX_ROUND = ["whole diff", "whole PR body", "Dry run", "Missed earlier"]
MARKED = "Missed earlier: the Plan command does not build the tests"


def review_at(when: str, lines: int, comment: bool = True) -> shapes.Graded:
    """A review that rejects the Plan and marks findings missed earlier.

    Args:
        when: when it was written.
        lines: how many findings it marks.
        comment: whether it is a regular review.

    Returns:
        The review.
    """
    mark = shapes.Verdict.CHANGES_NEEDED
    return dataclasses.replace(
        blank.GRADED,
        sha="a",
        when=when,
        plan=mark,
        execution=None,
        comment=comment,
        missed=lines,
    )


class TestBriefs(unittest.TestCase):
    """The briefs say it (Done-when 1, 2 and the fix round's)."""

    def test_a_first_round_says_to_list_every_finding(self) -> None:
        """Pitboss knows the round: nothing graded yet gives the first-round line."""
        for kind in STAGES:
            found = text(kind, graded="")
            has_all(found, [FIRST_ROUND])
            has_none(found, [LATER_ROUND, MISSED_EARLIER])

    def test_a_later_round_says_only_the_later_round(self) -> None:
        """Pitboss knows the round: a graded stage gives the later-round lines."""
        for kind in STAGES:
            found = text(kind, graded="execution")
            has_all(found, [LATER_ROUND, MISSED_EARLIER])
            has_none(found, [FIRST_ROUND])

    def test_the_review_after_a_fix_round_is_scoped_to_the_fixes(self) -> None:
        """The diff range, the clause and the approval, and no whole-Execution walk."""
        pinned(brief.Kind.REVIEW_FIX_ROUND, [FIX_ROUND_CLAUSE, FIX_ROUND_VERDICT])
        has_none(text(brief.Kind.REVIEW_FIX_ROUND), OUTSIDE_THE_FIX_ROUND)

    def test_the_other_briefs_do_not_carry_the_first_round(self) -> None:
        """A scoped review reads nothing outside its scope."""
        for kind in (brief.Kind.REVIEW_RESOLUTION, brief.Kind.REVIEW_RELOCK):
            has_none(text(kind), ["whole diff", "Dry run", "Missed earlier"])


class TestCount(unittest.TestCase):
    """The lines a review marks, and how the sweep splits them at the ruling."""

    def test_each_line_with_a_finding_counts(self) -> None:
        """A bare prefix says nothing and does not count."""
        body = f"## Review\n{MARKED} 1\n  {MARKED} 2\nMissed earlier:\nVerdict: x\n"
        assert_that(missed.count(body), equal_to(2))

    def test_a_review_without_the_line_counts_none(self) -> None:
        """A prefix inside a line does not count."""
        assert_that(missed.count("see Missed earlier: x\n"), equal_to(0))

    def test_the_counts_are_split_at_the_ruling(self) -> None:
        """Only regular reviews count, and a review at the ruling's time is before."""
        made = [
            review_at("1", 1),
            review_at("2", 2),
            review_at("3", 4),
            review_at("3", 8, comment=False),
        ]
        assert_that(missed.split(made, "2"), equal_to((3, 4)))
        assert_that(missed.split(made, ""), equal_to((7, 0)))
