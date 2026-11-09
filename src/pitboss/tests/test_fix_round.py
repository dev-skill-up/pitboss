"""The fix round: findings that name a file, and a refused Plan check (pitboss#390).

Keyword: fix-round-kind. The round that revises the Plan touches no code, doc or
test, so findings that name one are the fix round's, and so is a Plan check that
refused the Plan.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import plancheckflow, reviewfindings, shapes, steps
from ..markers import Marker
from . import test_flow
from . import test_flow_sweep as flows
from .suggestions import kind_of_third, next_output, third
from .test_flow import CHANGES, FIRST_REJECTION, OLDER, expect, graded, state
from .test_plan_check_step import (
    QUOTED,
    WITH_COMMANDS,
    check_comment,
    refused_comment,
)

FIX_ROUND = "fix round for the findings"
REVISE = "revise the plan"
NAMED = "Finding: false statements in doc/design.rst\n"
QUOTING = "Finding: row 3 fails: `pytest tests/test_x.py`; see https://x.org/a/b.py\n"


def naming(rejection: shapes.Comment, text: str) -> shapes.Comment:
    """A review comment with a line of findings after its form.

    Args:
        rejection: the review comment.
        text: the line.

    Returns:
        The comment.
    """
    return dataclasses.replace(rejection, body=rejection.body + text)


def rejecting_the_plan(
    names: bool, second: int = 1, sha: str = test_flow.HEAD
) -> shapes.Graded:
    """A review that rejects the Plan, as the flow reads it.

    Args:
        names: whether its findings name a file of the tree.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    review = graded(CHANGES, None, second, sha=sha)
    return dataclasses.replace(review, names_change=names)


class TestFindings(unittest.TestCase):
    """What a review's findings name."""

    def test_a_file_of_the_tree_is_a_change(self) -> None:
        """A doc, a source, a test, a line of one, a directory of the tree."""
        for text in (
            "false statements in doc/design.rst",
            "the helper in flow.py:12 is dead",
            "add a case to tests/test_flow.py",
            "src/pitboss/ must not import it",
            "plugins/pitboss/skills/sweep/SKILL.md says it",
        ):
            with self.subTest(text):
                assert_that(reviewfindings.names_change(text), equal_to(True))

    def test_a_quoted_command_a_link_and_prose_are_not(self) -> None:
        """The nearest inputs: the same path in a command, a link, or none."""
        for text in (
            "row 3 fails: `pytest doc/design.rst`",
            "see https://github.com/o/r/blob/main/doc/design.rst",
            "row 3 asks for no evidence; owner/repo#3 is the ticket",
            "slots heard must record hand-backs",
        ):
            with self.subTest(text):
                assert_that(reviewfindings.names_change(text), equal_to(False))


class TestFlow(unittest.TestCase):
    """Which round a rejected Plan is given."""

    def test_findings_that_name_a_file_get_the_fix_round(self) -> None:
        """A first rejection: the fix round beside the Plan revision."""
        expect(steps.fix_round(), state(rejecting_the_plan(True)))
        expect(steps.worker(steps.Task.REVISE_PLAN), state(rejecting_the_plan(False)))

    def test_a_second_rejection_is_ruled_whatever_the_findings_name(self) -> None:
        """Opus rules, as for any second Plan rejection."""
        first = rejecting_the_plan(True, 1, OLDER)
        expect(steps.opus_ruling(), state(first, rejecting_the_plan(True, 2)))

    def test_a_rejection_after_the_ruling_pauses(self) -> None:
        """The ruling was used and the Plan is still rejected."""
        pr = state(rejecting_the_plan(True, 4), comments=[test_flow.ruling(3)])
        expect(steps.pause_for_owner(), pr)

    def test_a_rejected_execution_is_ruled_first_whatever_it_names(self) -> None:
        """The Execution stage starts with the ruling."""
        review = dataclasses.replace(
            graded(*test_flow.EXECUTION_REJECTED, 1), names_change=True
        )
        expect(steps.opus_ruling(), state(review))

    def test_a_rejection_that_names_nothing_is_a_plan_revision(self) -> None:
        """The control: the stored first rejection names nothing."""
        expect(steps.worker(steps.Task.REVISE_PLAN), state(FIRST_REJECTION))


class TestPlanCheckRefusal(unittest.TestCase):
    """A Plan check that refused the current Plan."""

    def test_the_fix_round_is_offered_with_the_findings_quoted(self) -> None:
        """A kind of its own, a line that quotes, and no review."""
        refused = refused_comment(WITH_COMMANDS)
        here = flows.world_with([refused], body=WITH_COMMANDS)
        assert_that(kind_of_third(here), equal_to(FIX_ROUND))
        out = next_output(here)
        shown = [x for x in out.splitlines() if x.startswith(Marker.PR_STATE.text)]
        owned = [each for each in shown if "project#3" in each]
        assert_that(owned[0], contains_string("fix round: fix the findings"))
        assert_that(owned[0], contains_string(QUOTED))
        assert_that("(review it" in out, equal_to(False))

    def test_the_brief_names_the_check_and_quotes_it(self) -> None:
        """The task points at the comment of the check, not at a review."""
        refused = refused_comment(WITH_COMMANDS)
        brief = third(flows.world_with([refused], body=WITH_COMMANDS))[1]
        task = [line for line in brief if line.startswith("Task: ")]
        want = (
            "Task: PR owner/project#3: fix the findings of the Plan check at"
            f" {refused.url} ({QUOTED}), each one,"
        )
        assert_that(task[0], contains_string(want))
        assert_that(task[0], contains_string("run `pitboss nox` once"))

    def test_a_clean_check_offers_the_review_as_before(self) -> None:
        """The control: the same body with a clean check."""
        here = flows.world_with([check_comment(WITH_COMMANDS)], body=WITH_COMMANDS)
        assert_that(kind_of_third(here), equal_to("review the Plan and the Execution"))

    def test_long_findings_are_cut(self) -> None:
        """The quoted line has a limit."""
        refused = refused_comment(WITH_COMMANDS)
        long = dataclasses.replace(refused, body=refused.body + "x" * 700 + "\n")
        quoted = plancheckflow.findings(long)
        assert_that(len(quoted), equal_to(plancheckflow.QUOTED))
        assert_that(quoted.endswith("..."), equal_to(True))


class TestSweep(unittest.TestCase):
    """The kind a rejected Plan is listed as."""

    def test_the_kind_follows_the_findings(self) -> None:
        """A path in plain text is the fix round; none, or a quoted one, is not."""
        for text, kind in ((NAMED, FIX_ROUND), ("", REVISE), (QUOTING, REVISE)):
            with self.subTest(text):
                rejected = naming(flows.graded(flows.CHANGES, None, 1), text)
                assert_that(kind_of_third(flows.world_with([rejected])), equal_to(kind))
