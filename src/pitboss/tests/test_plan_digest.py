"""An approved Plan is never reopened (keyword: plan-digest, pitboss#172)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    bodydigest,
    brief,
    brieftext,
    flow,
    flowstate,
    plandigest,
    shapes,
    steps,
)
from . import blank, decisionline, fakes, world
from . import test_plan_digest_urls as urls
from .test_plan_digest_urls import pointed
from .briefmake import text as brief_text
from .test_commands import sweep
from .test_plan_digest_collapse import digest, legacy_digest
from .test_plan_digest_collapse import plan as expanded_plan
from .test_flow_sweep import (
    APPROVED,
    CHANGES,
    DIRTY,
    graded,
    world_with,
)
from .test_slot_commands import next_output
from .says import says

PLAN = fakes.PLAN_AND_EXECUTION
EDITED_PLAN = "## Plan\nthe plan, with a row added\n\n## Execution\nthe work\n"
EDITED_EXECUTION = "## Plan\nthe plan\n\n## Execution\nthe work, and more\n"


LINE = f"Plan digest: {digest(PLAN)}"
# keyword: one-path: the decisions of PR 3 the sweep and the list print
EDIT_LINE = "RULING: owner/project#3: the Plan was edited after its approval"
RULING_DUE = "RULING: owner/project#3: start an Opus agent"
RULING_WORDS = "revise the plan"
THIRD = "owner/project#3"
PLAN_DIGEST_START = "Plan digest: you grade the Plan, so add "
NO_PLAN = "## Execution\nwork\n"


def approving(second: int, digest_line: str | None = LINE) -> shapes.Comment:
    """A review that approves the Plan and rejects the Execution.

    Args:
        second: the second of the minute it was written.
        digest_line: its ``Plan digest:`` line, None for a review without one.

    Returns:
        The comment.
    """
    review = graded(APPROVED, CHANGES, second)
    if digest_line is None:
        return review
    return dataclasses.replace(review, body=review.body + digest_line + "\n")


def ruling(second: int, word: str = RULING_WORDS) -> shapes.Comment:
    """An Opus ruling comment.

    Args:
        second: the second of the minute it was written.
        word: what it rules.

    Returns:
        The comment.
    """
    return dataclasses.replace(
        blank.COMMENT,
        body=f"Opus ruling\nRuling: {word}\n",
        author_association="MEMBER",
        created_at=f"2026-10-30T00:00:{second:02d}Z",
    )


def looked_at(rounds: Sequence[shapes.Comment], body: str) -> tuple[str, str]:
    """What the sweep prints for PR 3, and PR 3's line of ``slots next``.

    Args:
        rounds: PR 3's comments.
        body: PR 3's body now.

    Returns:
        The sweep's line of PR 3, and its line in the list (empty when none).
    """
    here = world_with(rounds, body=body)
    swept = [x for x in sweep(here).out.splitlines() if "project#3 " in x]
    return "".join(swept), decisionline.of(next_output(here), "owner/project#3")


def plan_digest_run(text: str) -> tuple[object, str, str]:
    """Run ``pitboss plan-digest`` on a body.

    Args:
        text: the PR body, saved to a file.

    Returns:
        The exit code, the output and the error output.
    """
    done = world.invoke(world.make_world(), "plan-digest", saved(text))
    return done.code, done.out, done.err


def saved(text: str) -> str:
    """Save a body to a file.

    Args:
        text: the PR body.

    Returns:
        The file's name.
    """
    path = fakes.directory() / "body.txt"
    fakes.write(path, text)
    return str(path)


class TestThePlanSection(unittest.TestCase):
    """The text the Plan digest is of."""

    def test_the_section_runs_to_the_next_heading_without_head_lines(self) -> None:
        """Other sections, the Head line and line endings are not the Plan."""
        body = "intro\r\n## Plan\r\nrow\r\nHead: " + "a" * 40 + "\r\n## Evidence\r\nx"
        assert_that(plandigest.section(body), equal_to("## Plan\nrow"))
        assert_that(plandigest.section("## Plan\nrow"), equal_to("## Plan\nrow"))

    def test_a_body_without_a_plan_has_no_digest(self) -> None:
        """Nothing is compared for it."""
        assert_that(digest(NO_PLAN), equal_to(""))

    def test_an_execution_edit_keeps_the_digest(self) -> None:
        """Only the Plan section counts."""
        assert_that(digest(EDITED_EXECUTION), equal_to(digest(PLAN)))
        assert_that(digest(EDITED_PLAN) == digest(PLAN), equal_to(False))

    def test_the_recorded_line_is_read_whole(self) -> None:
        """Only a line that is exactly the prefix and 16 hex digits records one."""
        plan = digest(PLAN)
        cases = {
            f"Verdict: approved\nPlan digest: {plan}  \n": plan,
            f"Plan digest: {plan}x\n": "",
            f" Plan digest: {plan}\n": "",
            f"Body: {plan}\n": "",
            "Verdict: approved\n": "",
        }
        for body, expected in cases.items():
            with self.subTest(body):
                found = bodydigest.recorded_after(body, bodydigest.PLAN_PREFIX)
                assert_that(found, equal_to(expected))


class TestThePlanEditedLine(unittest.TestCase):
    """The sweep's line and the list of ``slots next``."""

    def test_an_edited_plan_is_named_and_offered_for_no_round(self) -> None:
        """The decision is the ruling on the edit, with the ruling brief for it.

        Keyword plan-edited-brief, quire#1115: no brief was offered, so one was
        built by hand.
        """
        here = world_with([approving(1)], body=EDITED_PLAN)
        swept, listed = looked_at([approving(1)], EDITED_PLAN)
        assert_that(swept, contains_string("review=changes-needed"))
        assert_that(listed, contains_string(EDIT_LINE))
        offered = next_output(here)
        assert_that(offered, contains_string("make an Opus ruling: owner/project#3"))
        assert_that(offered, contains_string("PITBOSS-SLOT: owner/project#3 ruling"))

    def test_the_sweep_prints_the_line(self) -> None:
        """The line names the PR and the way out."""
        out = sweep(world_with([approving(1)], body=EDITED_PLAN)).out
        assert_that(out, contains_string(EDIT_LINE))
        assert_that(out, contains_string("a ruling that says `revise the plan`"))

    def test_an_unedited_plan_has_no_line_and_the_ruling_is_due(self) -> None:
        """The Execution rejection is ruled on against the Plan as written."""
        for body in (PLAN, EDITED_EXECUTION):
            with self.subTest(body):
                out = sweep(world_with([approving(1)], body=body)).out
                assert_that(EDIT_LINE in out, equal_to(False))
                assert_that(out, contains_string(RULING_DUE))

    def test_a_review_without_a_plan_digest_is_not_checked(self) -> None:
        """Reviews written before the digest keep their flow."""
        out = sweep(world_with([approving(1, None)], body=EDITED_PLAN)).out
        assert_that(EDIT_LINE in out, equal_to(False))
        assert_that(out, contains_string(RULING_DUE))

    def test_the_newest_approving_review_with_a_digest_is_compared(self) -> None:
        """A newer approving review of the edited Plan answers the edit."""
        edited = f"Plan digest: {digest(EDITED_PLAN)}"
        rounds = [approving(1), approving(2, edited)]
        out = sweep(world_with(rounds, body=EDITED_PLAN)).out
        assert_that(EDIT_LINE in out, equal_to(False))
        assert_that(out, contains_string(RULING_DUE))

    def test_a_ruling_after_the_approval_allows_the_edit(self) -> None:
        """A ruling `revise the plan` written after the review lifts the line."""
        rounds = [approving(1), ruling(2)]
        out = sweep(world_with(rounds, body=EDITED_PLAN)).out
        assert_that(EDIT_LINE in out, equal_to(False))

    def test_a_rejected_plan_after_an_approval_is_not_revised_once_edited(self) -> None:
        """The approval still stands: no `revise the plan` round before a ruling."""
        rounds = [approving(1), graded(CHANGES, None, 2)]
        _, edited = looked_at(rounds, EDITED_PLAN)
        _, unedited = looked_at(rounds, PLAN)
        assert_that(edited, contains_string(EDIT_LINE))
        assert_that(unedited, contains_string(": revise the PLAN only"))

    def test_a_dirty_pr_with_an_edited_plan_is_ruled_on_first(self) -> None:
        """The edit is decided before the conflict: PLAN_EDITED is unresolved."""
        assert_that(steps.Step.PLAN_EDITED in steps.UNRESOLVED, equal_to(True))
        here = world_with([approving(1)], body=EDITED_PLAN, **DIRTY)
        out = sweep(here).out
        assert_that(out, contains_string(EDIT_LINE))
        third = decisionline.of(out, THIRD)
        assert_that("resolve the conflict" in third, equal_to(False))

    def test_a_ruling_before_the_approval_does_not(self) -> None:
        """The ruling must come after the approval."""
        here = world_with([ruling(1), approving(2)], body=EDITED_PLAN)
        says(sweep(here).out, EDIT_LINE)

    def test_a_ruling_of_another_word_is_executed_not_held(self) -> None:
        """pitboss#475: `do these steps` is offered at once, not PLAN EDITED."""
        rounds = [approving(1), ruling(2, "do these steps")]
        _, listed = looked_at(rounds, EDITED_PLAN)
        steps_line = ": do exactly the steps of the Opus ruling"
        assert_that(listed, contains_string(steps_line))


class TestTheDigestOfAPlanWithCiPointers(unittest.TestCase):
    """pitboss#475: the ids of a pointer's run and job are not the Plan."""

    def test_t475_only_the_urls_rewritten_is_no_edit_and_a_word_is(self) -> None:
        """Done-when 3: `plan_edited_without_ruling` is false, then true."""
        edit = urls.edited
        base, urls_only = pointed(1, 2), pointed(77, 88)
        found = [
            flowstate.plan_edited_without_ruling(edit(base, now))
            for now in (urls_only, pointed(77, 88, "test"))
        ]
        assert_that(found, equal_to([False, True]))

    def test_t475_a_revision_then_do_these_steps_is_not_plan_edited(self) -> None:
        """Done-when 1: the approving review, the edited Plan, both rulings."""
        pr = urls.edited(urls.PLAN, urls.EDITED_PLAN, urls.revised_then_steps(3))
        assert_that(
            steps.step_of(flow.next_step(pr)) is steps.Step.PLAN_EDITED, equal_to(False)
        )


class TestTheOldDigestIsStillAccepted(unittest.TestCase):
    """A digest recorded before the expanded blocks were collapsed (pitboss#399)."""

    def test_the_digest_before_the_collapse_is_no_longer_the_plan_read(self) -> None:
        """pitboss#399: the sweep prints PLAN EDITED for the digest of the old form."""
        for read, edited in (
            (expanded_plan(), True),
            (expanded_plan(prose="o\n"), True),
        ):
            with self.subTest(edited):
                line = f"Plan digest: {legacy_digest(read)}"
                body = expanded_plan()
                out = sweep(world_with([approving(1, line)], body=body)).out
                assert_that(EDIT_LINE in out, equal_to(edited))


class TestTheCommand(unittest.TestCase):
    """``pitboss plan-digest`` prints the line a review of the Plan records."""

    def test_it_prints_the_line_or_exits_2_without_a_plan(self) -> None:
        """The digest of the Plan section; a body with none prints nothing."""
        results = {text: plan_digest_run(text) for text in (PLAN, NO_PLAN)}
        assert_that(results[PLAN], equal_to((0, LINE + "\n", "")))
        assert_that(results[NO_PLAN][:2], equal_to((2, "")))
        assert_that(results[NO_PLAN][2], contains_string("no `## Plan` section"))


class TestTheBriefs(unittest.TestCase):
    """The briefs say that an approved Plan is not edited."""

    def test_each_sentence_is_in_the_briefs_it_belongs_to(self) -> None:
        """Who is told not to edit the Plan, who not to ask for it, who records it."""
        Kind = brief.Kind
        belongs = {
            brieftext.NO_PLAN_EDIT: {
                Kind.FIX_REVIEW,
                Kind.FIX_CI,
                Kind.RESOLVE_CONFLICT,
                Kind.RULING_STEPS,
                Kind.RUN_PLAN,
                Kind.ADD_CI_QUOTES,
            },
            brieftext.NO_PLAN_FINDING: {Kind.REVIEW_EXECUTION, Kind.REVIEW_FIX_ROUND},
            PLAN_DIGEST_START: {Kind.REVIEW_FULL, Kind.REVIEW_PLAN},
        }
        for sentence, kinds in belongs.items():
            found = {kind for kind in Kind if sentence in brief_text(kind)}
            with self.subTest(sentence):
                assert_that(found, equal_to(kinds))

    def test_a_plan_problem_is_handed_back_as_not_proceeding(self) -> None:
        """The worker's sentence names the hand-back and the evidence."""
        assert_that(
            brieftext.NO_PLAN_EDIT,
            contains_string("as NOT PROCEEDING with the evidence"),
        )
