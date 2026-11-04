"""The briefs say a Plan relies on CI for what CI shows (pitboss#179)."""

import unittest

from hamcrest import assert_that, contains_string

from .. import brief
from .briefmake import has_none, pinned, text
from .test_brief_nox import PLAN_WRITERS, WORKERS
from .test_evidence_rules import read, words
from .test_plan_commands import PLAN_REVIEWS, PLAN_RUNNING

PLAN_CI = (
    "CI pointer: a Plan row whose result a CI run of the commit shows asks for no"
    " long local command (a whole suite or build, or anything over `timeout"
    " 598`); it points to CI and names the workflow, the step of the run's log, a"
    " greppable string that step prints (a test name or a line), and how the run"
    " is found for the commit (the run and job URL `actions` gives for the head)."
    " Evidence in the PR body is only for what CI does not show (pitboss#179)."
)
BODY_CI = (
    "CI in the body: for a row the Plan points to CI, the PR body gives no"
    " evidence and holds only the pointer, with the run and job URL found for the"
    " head, the workflow, the step and the greppable string; evidence in the PR"
    " body is only for what CI does not show (pitboss#179)."
)
REVIEW_CI = (
    "CI pointer: a Plan row that asks for a long local command (a whole suite or"
    " build, or anything over `timeout 598`) whose result a CI run of the commit"
    " shows is changes needed; so is a row that points to CI without the"
    " workflow, the step, a greppable string and how the run is found for the"
    " commit (pitboss#179)."
)
NOT_WRITING = tuple(kind for kind in WORKERS if kind not in PLAN_WRITERS)


class TestCiPointer(unittest.TestCase):
    """The three briefs carry the rule, and the Plan review enforces it."""

    def test_the_plan_brief_says_a_row_points_to_ci_by_name(self) -> None:
        """Every brief that writes a Plan carries the pointer rule."""
        for kind in PLAN_WRITERS:
            pinned(kind, [PLAN_CI])
        for kind in NOT_WRITING:
            has_none(text(kind), [PLAN_CI])

    def test_the_worker_brief_gives_no_evidence_for_a_ci_row(self) -> None:
        """The PR body holds the pointer only for a row CI shows."""
        for kind in PLAN_RUNNING:
            pinned(kind, [BODY_CI])
        has_none(text(brief.Kind.REVISE_PLAN), [BODY_CI])

    def test_the_plan_review_rejects_a_long_command_and_a_bare_pointer(self) -> None:
        """A long local command CI shows, or a pointer without names, is rejected."""
        for kind in PLAN_REVIEWS:
            pinned(kind, [REVIEW_CI])
        has_none(text(brief.Kind.REVIEW_EXECUTION), [REVIEW_CI])

    def test_the_reference_holds_the_rule_the_briefs_carry(self) -> None:
        """adversarial-review.md has the pointer and review wording."""
        reference = words(read("adversarial-review.md"))
        pointer = PLAN_CI.removeprefix("CI pointer: a ").split(";")[0]
        assert_that(reference, contains_string(pointer))
        sentence = REVIEW_CI.removeprefix("CI pointer: a ").split(" (pitboss")[0]
        assert_that(reference, contains_string(sentence))
