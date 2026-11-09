"""The briefs carry the Plan's precise-commands rule (pitboss#159)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftext, brieftextexec
from .briefmake import has_none, pinned, text
from .test_evidence_rules import read, words

BODY = (
    "for each Done-when row, if the Plan's evidence mentions a command, the Plan"
    " must give the precise command (the exact string to run on the head, a cut"
    " or a pipe included when the Plan wants one); a row that mentions a command"
    " without it is a changes-needed finding of the Plan. Evidence that is not a"
    " command (a file read, a diff) is accepted when the Plan says exactly what"
    " will be shown; a CI run is accepted only as a CI pointer (the CI pointer"
    " rule)."
)
EXECUTION = (
    "grade the Execution against the Plan as written; each precise command of"
    " the Plan must have been run as written; a command run in another form, or"
    " left out, is a changes-needed finding. Cutting or piping the output of a"
    " command run exactly as the Plan wrote it is allowed and is never a finding;"
    " a finding is a different command (another word, file or option), a command"
    " left out, or a cut that hides the line the row asks to show."
)
CUT_ALLOWED = (
    "Cutting or piping the output of a command run exactly as the Plan wrote it"
    " is allowed and is never a finding; a finding is a different command"
    " (another word, file or option), a command left out, or a cut that hides"
    " the line the row asks to show."
)
WORKER = (
    "run each precise command of the Plan as written; if the Plan's command"
    " cannot show its row, change the Plan first and ask for its review."
)
PLAN_REVIEWS = (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_PLAN)
EXECUTION_REVIEWS = (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION)
PLAN_RUNNING = (
    brief.Kind.NEW_PR,
    brief.Kind.FIRST_ROUND,
    brief.Kind.FIX_REVIEW,
    brief.Kind.FIX_ROUND,
)
OTHERS = (
    brief.Kind.REVISE_PLAN,
    brief.Kind.FIX_CI,
    brief.Kind.RESOLVE_CONFLICT,
    brief.Kind.REVIEW_RESOLUTION,
    brief.Kind.REVIEW_FIX_ROUND,
    brief.Kind.REVIEW_RELOCK,
    brief.Kind.RULING,
)


class TestPlanCommands(unittest.TestCase):
    """The Plan names its commands, the worker runs them, the review checks."""

    def test_the_plan_review_rejects_a_command_without_its_precise_form(self) -> None:
        """Done-when 1: the Plan and full review briefs say it."""
        for kind in PLAN_REVIEWS:
            pinned(kind, [BODY])

    def test_the_execution_review_grades_against_the_plan_as_written(self) -> None:
        """Done-when 2: the Execution and full review briefs say it."""
        for kind in EXECUTION_REVIEWS:
            pinned(kind, [EXECUTION])

    def test_the_execution_review_allows_a_cut_of_the_output(self) -> None:
        """pitboss#195: the brief says a cut or a pipe is never a finding."""
        for kind in EXECUTION_REVIEWS:
            pinned(kind, [CUT_ALLOWED])
        reference = words(read("adversarial-review.md"))
        assert_that(reference.count(CUT_ALLOWED), equal_to(1))

    def test_the_worker_runs_each_command_as_written(self) -> None:
        """Done-when 3: the worker briefs that run a Plan say it."""
        for kind in PLAN_RUNNING:
            pinned(kind, [WORKER])

    def test_the_other_briefs_do_not_carry_it(self) -> None:
        """A brief with no Plan to grade or run says nothing of it."""
        for kind in OTHERS:
            has_none(text(kind), ["Plan commands:"])
        has_none(text(brief.Kind.REVIEW_PLAN), [EXECUTION])
        has_none(text(brief.Kind.REVIEW_EXECUTION), [BODY])

    def test_the_reference_holds_the_wording_the_briefs_carry(self) -> None:
        """Done-when 4: the reference has each sentence, and the briefs the same."""
        reference = words(read("adversarial-review.md"))
        for sentence in (BODY, EXECUTION, WORKER):
            assert_that(reference, contains_string(sentence))
        for each in (
            brieftext.PLAN_COMMANDS_PLAN,
            brieftextexec.PLAN_COMMANDS_EXECUTION,
            brieftext.PLAN_COMMANDS_WORKER,
        ):
            assert_that(each.startswith("Plan commands: "), equal_to(True))
            assert_that(
                words(each).removeprefix("Plan commands: ") in reference,
                equal_to(True),
            )
