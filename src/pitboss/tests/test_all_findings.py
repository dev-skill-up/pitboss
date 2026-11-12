"""A review lists every finding in one round; the later round checks those (#169)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, missed, shapes
from . import test_brief, test_flow, test_flow_sweep as flows
from .briefmake import APPROVED, HEAD, PLAN_REVIEWS, pinned, text
from .says import has_none
from .test_commands import sweep

FIRST_ROUND = (
    "in the first round of a stage, read the whole PR body, the whole diff and"
    " every command of the Plan against the repository, and list every finding of"
    " the stage you grade in that one review, not the first few. A later round on"
    " the same stage (an earlier review of this PR graded it) checks only the"
    " earlier findings and the findings caused by the changes made since the head"
    " that review read."
)
MISSED_EARLIER = (
    "a review that is not the first round and raises a finding that is present in"
    " the unchanged text of an earlier head says so, with one line for each such"
    " finding that starts with `Missed earlier:` and says what the finding is;"
    " the sweep counts those lines for the analysis of the rounds after an Opus"
    " ruling."
)
DRY_RUN = (
    "in a review of the Plan, try each command of the Plan as a read-only dry run"
    " where it can be tried (it changes nothing in the repository, the PR or the"
    " machine), and report each that cannot run as written as a finding of the"
    " Plan."
)
FIX_ROUND_CLAUSE = (
    f"The diff to read is `git diff {APPROVED}..{HEAD}`. Check that each finding"
    f" is fixed at head {HEAD} as the finding asks, whether the fixes invalidate"
    " the approved Plan, and the CI on the head, and nothing else. You may raise"
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


def marked(review: shapes.Comment, lines: int) -> shapes.Comment:
    """A review with lines that mark findings missed earlier.

    Args:
        review: the review comment.
        lines: how many lines to add.

    Returns:
        The comment with those lines after its ``Verdict:`` line.
    """
    added = "".join(f"{MARKED} {n}\n" for n in range(lines))
    return dataclasses.replace(review, body=review.body + added)


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
    return shapes.Graded(
        sha="a", when=when, plan=mark, execution=None, comment=comment, missed=lines
    )


class TestBriefs(unittest.TestCase):
    """The briefs say it (Done-when 1, 2 and the fix round's)."""

    def test_a_review_of_a_stage_lists_every_finding_in_the_first_round(self) -> None:
        """Done-when 1: the whole body, the whole diff, every Plan command."""
        for kind in STAGES:
            pinned(kind, [FIRST_ROUND])

    def test_a_plan_review_tries_each_plan_command_as_a_dry_run(self) -> None:
        """Done-when 2: the commands that cannot run as written are reported."""
        for kind in PLAN_STAGES:
            pinned(kind, [DRY_RUN])
        has_none(text(brief.Kind.REVIEW_EXECUTION), ["Dry run:"])

    def test_only_a_plan_review_runs_anything(self) -> None:
        """The line that says a reviewer runs nothing names the dry runs."""
        for kind in brief.REVIEWS:
            runs = kind in PLAN_STAGES
            says = "You run nothing but the dry runs of the Plan's commands:"
            assert_that(says in text(kind), equal_to(runs))

    def test_a_later_round_says_a_finding_was_missed_earlier(self) -> None:
        """Done-when 3: the line the sweep counts."""
        for kind in STAGES:
            pinned(kind, [MISSED_EARLIER])

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


class TestSweep(unittest.TestCase):
    """PAUSE counts the findings marked missed earlier, before and after the ruling."""

    def test_pause_counts_the_findings_marked_missed_earlier(self) -> None:
        """Done-when 3: one before the ruling, two after it."""
        rounds = [
            marked(flows.graded(flows.CHANGES, None, 1, sha=flows.OLDER), 1),
            flows.graded(flows.CHANGES, None, 2),
            test_flow.ruling(3),
            marked(flows.graded(flows.CHANGES, None, 4), 2),
        ]
        swept = sweep(flows.world_with(rounds)).out
        assert_that(swept, contains_string(flows.PAUSE_LINE))
        assert_that(
            swept,
            contains_string(
                "findings the reviews mark `missed earlier`: 2 after the ruling,"
                " 1 before it"
            ),
        )

    def test_the_other_ruling_lines_print_no_count(self) -> None:
        """RULING DUE is before any ruling and prints none."""
        swept = sweep(flows.world_with(flows.TWO_PLAN_REJECTIONS)).out
        assert_that(swept, contains_string(flows.RULING_LINE))
        assert_that("missed earlier" in swept, equal_to(False))
