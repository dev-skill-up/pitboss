"""The spellings the form check accepts are the ones the sweep reads (rp#684).

On repository-prototype#684 (grade-spellings) a reviewer posted
``Plan: ok``; the form check read only the first line and accepted it, the sweep
read no grade in it, and a second Plan review was offered. Each verdict form
(Plan, Execution, the ``Verdict:`` line, the fixed Plan line of a re-review, the
merge-proof comment, the Opus ruling) has one definition that both sides use,
and this test derives the spellings each side accepts and compares them.
"""

import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length, is_not

from .. import (
    config,
    flowstate,
    forms,
    gradeline,
    reviewrules,
    reviews,
    rulingform,
    rulingwords,
    shapes,
    unreadableform,
)
from . import fakes, world

HEAD = "a" * 40
FORM = config.DEFAULT_REVIEW_FORM
SPELLINGS = (
    "approved",
    "changes needed",
    "approved (fixed)",
    "approved. The audit row now holds",
    "approved Review of the Plan alone",
    "ok",
    "OK",
    "Approved",
    "LGTM",
    "approve",
    "changes-needed",
    "",
    "(approved)",
    "approved.",
    "approved,",
    "approved;",
    "approved:",
    "approved.   ",
    "approved   ",
    "approved.\t",
    "approved!",
    "changes needed.",
    "Changes needed.",
)
# keyword: grade-spellings (quire#1116): whole Plan lines, with the marks and the
# spacing a reviewer may type around the verdict; each is judged by both sides
LINES = (
    "Plan: approved.",
    "Plan: approved.   ",
    "Plan: approved\t",
    "**Plan: approved**",
    "**Plan:** approved",
    "*Plan: approved*",
    "__Plan: approved__",
    "plan: approved",
    "PLAN: approved",
    "Plan:approved",
    "Plan : approved",
    "Plan:  approved",
    "Plan:\tapproved",
    "Plan: **approved**",
)
Judge = Callable[[str], bool]


def _comment(plan: str) -> str:
    return (
        f"## Review\nReviewed: {HEAD}\nPlan: {plan}\nExecution: approved\n"
        "Verdict: approved\n"
    )


def accepted_by_the_form_check(body: str) -> bool:
    """Whether the form check of a review says nothing of its grade lines.

    Args:
        body: the review comment.

    Returns:
        True when no finding is made.
    """
    return not reviewrules.grade_findings(body, FORM)


def read_by_the_sweep(body: str) -> bool:
    """Whether the sweep reads a grade in the Plan line.

    Args:
        body: the review comment.

    Returns:
        True when the comment, read as a review, has a graded Plan line.
    """
    read = reviews.read_comment(body, FORM)
    return read is not None and (
        gradeline.line_approved(
            body, gradeline.PLAN_PREFIX, "approved", "changes needed"
        )
        is not None
    )


def _comment_line(plan_line: str) -> str:
    return (
        f"## Review\nReviewed: {HEAD}\n{plan_line}\nExecution: approved\n"
        "Verdict: approved\n"
    )


def differing_lines(accepts: Judge, reads: Judge) -> Sequence[str]:
    """The whole Plan lines one side accepts and the other does not read.

    Args:
        accepts: the form check's judgement of a review.
        reads: the sweep's judgement of it.

    Returns:
        Each line of ``LINES`` the two sides judge differently.
    """
    return [
        each
        for each in LINES
        if accepts(_comment_line(each)) != reads(_comment_line(each))
    ]


def differing(accepts: Judge, reads: Judge) -> Sequence[str]:
    """The spellings one side accepts and the other does not.

    Args:
        accepts: the form check's judgement of a review.
        reads: the sweep's judgement of it.

    Returns:
        Each Plan spelling the two sides judge differently.
    """
    return [
        each for each in SPELLINGS if accepts(_comment(each)) != reads(_comment(each))
    ]


def lint_review(plan: str) -> world.Result:
    """Run the command a review brief names on a review with a Plan line.

    Args:
        plan: what follows ``Plan: `` in the review.

    Returns:
        What ``pitboss lint review FILE --head HEAD`` did.
    """
    here = world.make_world()
    path = fakes.directory() / "review.md"
    path.write_text(_comment(plan))
    return world.invoke(here, "lint", "review", str(path), "--head", HEAD)


class TestGradeSpellings(unittest.TestCase):
    """One definition of a grade line, used by both sides."""

    def test_the_form_check_accepts_exactly_what_the_sweep_reads(self) -> None:
        """Derived from the code, for every spelling tried, Plan and Execution."""
        assert_that(differing(accepted_by_the_form_check, read_by_the_sweep), empty())

    def test_c19_the_form_check_accepts_exactly_the_lines_the_sweep_reads(self) -> None:
        """Trailing marks, whitespace, case, bold and colon spacing (quire#1116)."""
        assert_that(
            differing_lines(accepted_by_the_form_check, read_by_the_sweep), empty()
        )

    def test_c19_a_trailing_full_stop_and_trailing_space_grade_like_the_bare_word(
        self,
    ) -> None:
        """The pattern both sides share reads ``Plan: approved.`` as an approval."""
        for line in ("Plan: approved.", "Plan: approved.  ", "Plan: approved\t"):
            with self.subTest(line):
                graded = gradeline.line_approved(line, "Plan: ", "approved", "x")
                assert_that(graded, equal_to(True))

    def test_c19_a_marked_up_or_misspaced_line_is_refused_with_the_words_printed(
        self,
    ) -> None:
        """Bold, other case and a space before the colon are named, not skipped."""
        for line in ("**Plan: approved**", "plan: approved", "Plan : approved"):
            with self.subTest(line):
                found = reviewrules.grade_findings(_comment_line(line), FORM)
                assert_that(found, has_length(1))
                assert_that(found[0], contains_string("`Plan: approved`"))
                assert_that(found[0], contains_string("`Plan: changes needed`"))

    def test_c19_the_form_note_rules_out_bold_case_and_a_space_before_the_colon(
        self,
    ) -> None:
        """What ``review-form`` prints, and a brief carries, names the exclusions."""
        for word in ("bold", "space before the colon", "`.`"):
            assert_that(gradeline.FORM_NOTE, contains_string(word))

    def test_plan_ok_is_refused_by_the_form_check_rp_684(self) -> None:
        """The state of rp#684: ``Plan: ok`` grades nothing and is named."""
        found = reviewrules.grade_findings(_comment("ok"), FORM)
        assert_that(found, has_length(1))
        assert_that(
            "`Plan: ok`" in found[0] or "'Plan: ok'" in found[0], equal_to(True)
        )

    def test_planted_a_form_check_that_reads_the_first_line_only_differs(self) -> None:
        """Planted: the old check accepted every spelling; the test finds the split."""
        found = differing(lambda _: True, read_by_the_sweep)
        assert_that("ok" in found and "approved" not in found, equal_to(True))

    def test_the_sweep_names_a_comment_with_an_ungraded_line(self) -> None:
        """``slots next`` and the sweep print the UNREADABLE REVIEW line for it."""
        comment = shapes.Comment(
            body=_comment("ok"),
            author_association="MEMBER",
            created_at="2026-11-11T00:00:00Z",
            url="https://example/1",
        )
        found = unreadableform.find(
            [comment], frozenset({"MEMBER"}), FORM, reviews.line_pattern
        )
        assert_that(found, has_length(1))
        assert_that("grades nothing" in found[0].problem, equal_to(True))

    def test_execution_lines_are_judged_as_plan_lines_are(self) -> None:
        """The same definition grades the Execution line."""
        body = f"## Review\nReviewed: {HEAD}\nExecution: ok\nVerdict: approved\n"
        assert_that(
            gradeline.ungraded(body, "approved", "changes needed"), has_length(1)
        )

    def test_the_fixed_plan_line_of_a_re_review_is_read_as_approved(self) -> None:
        """Re-review: the line pitboss tells a reviewer to write is a grade."""
        body = f"{gradeline.fixed_line(FORM.approved)}\n"
        assert_that(gradeline.ungraded(body, "approved", "changes needed"), empty())
        assert_that(
            gradeline.line_approved(body, gradeline.PLAN_PREFIX, "approved", "x"),
            equal_to(True),
        )

    def test_the_split_check_reads_the_form_words_not_its_own(self) -> None:
        """A form with other words is split by the same definition."""
        other = config.ReviewForm(lines=FORM.lines, approved="ok", changes_needed="no")
        body = "Plan: ok\nExecution: no\n"
        assert_that(reviewrules.is_split(body, other), equal_to(True))
        assert_that(reviewrules.is_split(body), equal_to(False))

    def test_the_merge_proof_comment_is_a_review_in_the_same_form(self) -> None:
        """A main-merge comment: ``Verdict: approved`` is read, ``OK`` is not."""
        for word, read in (("approved", True), ("changes needed", True), ("OK", False)):
            with self.subTest(word):
                body = f"## Review\nReviewed: {HEAD}\nVerdict: {word}\n"
                found = reviews.read_comment(body, FORM) is not None
                subject = forms.Subject(name="review", body=body, head=HEAD)
                clean = not forms.ordinary_review(subject, FORM)
                assert_that((found, clean), equal_to((read, read)))

    def test_every_ruling_word_the_form_accepts_the_sweep_reads(self) -> None:
        """Rulings: derived from the enum, both sides use ``rulingwords``."""
        for ruling in rulingwords.Ruling:
            with self.subTest(ruling.value):
                text = f"Opus ruling\nRuling: {ruling.value}\n\nHow we got here\n- x\n"
                accepted = rulingform.refusal(text) == ""
                assert_that(accepted, equal_to(True))
                assert_that(flowstate.read_ruling(text), equal_to(ruling))
        bad = "Opus ruling\nRuling: ok\n\nHow we got here\n- x\n"
        assert_that(rulingform.refusal(bad), is_not(equal_to("")))
        assert_that(flowstate.read_ruling(bad), equal_to(None))

    def test_the_command_the_brief_names_refuses_plan_ok_and_passes_approved(
        self,
    ) -> None:
        """``lint review`` is the pre-post check: exit 1 naming the line, else ok."""
        refused, passed = lint_review("ok"), lint_review("approved")
        said = [("review-grade" in each.out, each.code) for each in (refused, passed)]
        assert_that(said, equal_to([(True, 1), (False, 0)]))

    def test_quire_1110_a_prose_plan_line_is_refused_with_the_words_printed(
        self,
    ) -> None:
        """Quire 1110: a prose ``Plan:`` line is named, never ignored."""
        prose = (
            "the Plan covers every Done-when item",
            "sound, every row has its command",
            "Approved by me",
        )
        for line in prose:
            with self.subTest(line):
                found = reviewrules.grade_findings(_comment(line), FORM)
                assert_that(found, has_length(1))
                assert_that(found[0], contains_string(f"Plan: {line}"))
                assert_that(found[0], contains_string("`Plan: approved`"))
                assert_that(found[0], contains_string("`Plan: changes needed`"))
                assert_that(read_by_the_sweep(_comment(line)), equal_to(False))
