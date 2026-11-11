"""The fix round: findings that name a file, and a refused Plan check (pitboss#390).

The round that revises the Plan touches no code, doc or test, so findings that
name one are the fix round's (keyword: fix-round-kind), and so is a Plan check
that refused the Plan.
"""

import dataclasses
import unittest
from typing import Tuple

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, plancheck, plancheckflow, plandigest, reviewfindings, shapes, steps
from ..markers import Marker
from . import test_flow, world
from . import test_flow_sweep as sweeps
from .suggestions import kind_of_third, next_output, third
from .test_flow import CHANGES, OLDER, expect, graded, state
from .test_plan_check_step import (
    NO_COMMANDS,
    QUOTED,
    WITH_COMMANDS,
    check_comment,
    refused_comment,
)

FIX_ROUND = "fix round for the findings"
REVISE = "revise the plan"
NAMED = "Finding: false statements in doc/index.rst\n"
QUOTING = "Finding: row 3 fails: `pytest tests/test_x.py`; see https://x.org/a/b.py\n"
PLAN_FIX = steps.worker(steps.Task.FIX_ROUND)
PLAN_REVISION = steps.worker(steps.Task.REVISE_PLAN)


def said(second: int, text: str, author: str = "MEMBER") -> shapes.Comment:
    """The comment of a review, with the text of its findings.

    Args:
        second: the second of the minute it was written.
        text: its findings.
        author: its author's association.

    Returns:
        The comment.
    """
    when = f"2026-10-30T00:00:{second:02d}Z"
    return shapes.Comment(
        body=text, author_association=author, created_at=when, url="https://x.org/r"
    )


Rejection = Tuple[shapes.Graded, shapes.Comment]


def rejecting(text: str, second: int = 1, sha: str = test_flow.HEAD) -> Rejection:
    """A review that rejects the Plan, and the comment it was read from.

    Args:
        text: its findings.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The review and its comment.
    """
    return graded(CHANGES, None, second, sha=sha), said(second, text)


def rejected_pr(*given: Rejection) -> flow.PullState:
    """The state of a PR with these reviews, each with its comment.

    Args:
        *given: pairs of a review and its comment.

    Returns:
        The state.
    """
    return state(*(each[0] for each in given), comments=[each[1] for each in given])


def refused_world() -> Tuple[shapes.Comment, world.World]:
    """A world whose PR 3 has a Plan with commands that a check refused.

    Returns:
        The refusing comment and the world.
    """
    refused = refused_comment(WITH_COMMANDS)
    return refused, sweeps.world_with([refused], body=WITH_COMMANDS)


class TestFindings(unittest.TestCase):
    """What a review names."""

    def test_a_file_of_the_tree_is_a_change(self) -> None:
        """A doc, a source, a test, a line of one, a directory of the tree."""
        for text in (
            "false statements in doc/index.rst",
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
            "row 3 fails: `pytest doc/index.rst`",
            "see https://github.com/o/r/blob/main/doc/index.rst",
            "row 3 asks for no evidence; owner/repo#3 is the ticket",
            "slots heard must record hand-backs",
        ):
            with self.subTest(text):
                assert_that(reviewfindings.names_change(text), equal_to(False))

    def test_only_a_trusted_comment_of_that_time_counts(self) -> None:
        """The time and the author select the review's own comment."""
        member, other = said(1, NAMED), said(1, NAMED, "NONE")
        named = reviewfindings.named_by
        found = (
            named([member], {"MEMBER"}, member.created_at),
            named([other], {"MEMBER"}, other.created_at),
            named([member], {"MEMBER"}, said(9, NAMED).created_at),
        )
        assert_that(found, equal_to((True, False, False)))


class TestFlow(unittest.TestCase):
    """Which round a rejected Plan is given."""

    def test_findings_that_name_a_file_get_the_fix_round(self) -> None:
        """A first rejection: the fix round beside the Plan revision."""
        expect(PLAN_FIX, rejected_pr(rejecting(NAMED)))
        expect(PLAN_REVISION, rejected_pr(rejecting("Finding: row 3 is vague\n")))

    def test_a_second_rejection_is_ruled_whatever_the_findings_name(self) -> None:
        """Opus rules, as for any second Plan rejection."""
        pr = rejected_pr(rejecting(NAMED, 1, OLDER), rejecting(NAMED, 2))
        expect(steps.opus_ruling(), pr)

    def test_a_rejection_after_the_ruling_pauses(self) -> None:
        """The ruling was used and the Plan is still rejected."""
        here = rejected_pr(rejecting(NAMED, 4))
        pr = dataclasses.replace(here, comments=[*here.comments, test_flow.ruling(3)])
        expect(steps.pause_for_owner(), pr)

    def test_a_rejected_execution_is_ruled_first_whatever_it_names(self) -> None:
        """The Execution stage starts with the ruling."""
        review = graded(*test_flow.EXECUTION_REJECTED, 1)
        expect(steps.opus_ruling(), state(review, comments=[said(1, NAMED)]))


class TestPlanCheckRefusal(unittest.TestCase):
    """A Plan check that refused the current Plan."""

    def test_the_fix_round_is_offered_with_the_findings_quoted(self) -> None:
        """A kind of its own, a line that quotes, and no review."""
        refused, here = refused_world()
        assert_that(kind_of_third(here), equal_to(FIX_ROUND))
        out = next_output(here)
        shown = [x for x in out.splitlines() if x.startswith(Marker.PR_STATE.text)]
        owned = [each for each in shown if "project#3" in each]
        assert_that(owned[0], contains_string("fix round: fix the findings"))
        assert_that(owned[0], contains_string(QUOTED))
        assert_that("(review it" in out, equal_to(False))

    def test_the_brief_names_the_check_and_quotes_it(self) -> None:
        """The task points at the comment of the check, not at a review."""
        refused, here = refused_world()
        brief = third(here)[1]
        task = [line for line in brief if line.startswith("Task: ")]
        want = (
            "Task: PR owner/project#3: fix the findings of the Plan check at"
            f" {refused.url} ({QUOTED}), each one,"
        )
        assert_that(task[0], contains_string(want))
        assert_that(task[0], contains_string("run `pitboss nox` once"))

    def test_a_refused_plan_with_no_command_is_a_fix_brief_with_the_findings(
        self,
    ) -> None:
        """The refusal is the Plan's findings, not its commands (the slot line)."""
        found = "Done-when findings: the digest line is missing"
        section = plandigest.section(NO_COMMANDS)
        refused = dataclasses.replace(
            check_comment(NO_COMMANDS),
            body=plancheck.text(section, [], [], [found]),
        )
        here = sweeps.world_with([refused], body=NO_COMMANDS)
        assert_that(kind_of_third(here), equal_to(FIX_ROUND))
        out = next_output(here)
        assert_that(out, contains_string("PITBOSS-SLOT: owner/project#3 fix"))
        assert_that("PITBOSS-SLOT: owner/project#3 review" in out, equal_to(False))
        assert_that(" ".join(third(here)[1]), contains_string(found))

    def test_a_clean_check_offers_the_review_as_before(self) -> None:
        """The control: the same body with a clean check."""
        here = sweeps.world_with([check_comment(WITH_COMMANDS)], body=WITH_COMMANDS)
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
                review = sweeps.graded(sweeps.CHANGES, None, 1)
                rejected = dataclasses.replace(review, body=review.body + text)
                assert_that(
                    kind_of_third(sweeps.world_with([rejected])), equal_to(kind)
                )
