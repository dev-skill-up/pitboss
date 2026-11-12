"""Every brief that names a required line says its exact words (grade-spellings).

Post-mortem of repository-prototype#684: the review brief said "write a `Plan:`
line", named no word, and named no command to check the comment with; the
reviewer wrote ``Plan: ok``. Each form below (the grade lines, the Verdict and
Reviewed lines, Head, Evidence, the footer, the Plan check comment, the ruling
and the hand-back) is a row: the briefs that name it, the text each prints taken
from the constant the check uses, and the check command the brief names.
"""

import unittest

from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    brief,
    briefgrade,
    briefkind,
    config,
    gradeline,
    rulingwords,
    steps,
)
from . import briefmake

FORM = config.DEFAULT_REVIEW_FORM
WORDS = f"<{FORM.approved} or {FORM.changes_needed}>"
REVIEWS = tuple(briefkind.REVIEWS)
WORKERS = tuple(
    each for each in brief.Kind if each not in REVIEWS and each.name != "RULING"
)
PLAN_AND_BODY = tuple(brief.PLAN_RUNNERS)


def printed(kind: brief.Kind, **changes: object) -> str:
    """The brief of a kind.

    Args:
        kind: the kind.
        **changes: fields to replace.

    Returns:
        Its text.
    """
    return briefmake.text(kind, **changes)


def named_in_every(each: Sequence[brief.Kind], words: Sequence[str]) -> None:
    """Check that the brief of each kind contains each needle.

    Args:
        each: the kinds of brief.
        words: the texts each brief must contain.
    """
    for made in each:
        with unittest.TestCase().subTest(made.name):
            for phrase in words:
                assert_that(printed(made), contains_string(phrase))


class TestGradeLines(unittest.TestCase):
    """B-forms: the Plan and Execution lines, with the words the check reads."""

    def test_every_review_brief_prints_the_grade_lines_of_its_kind(self) -> None:
        """Derived from ``gradeline``: the line prefix and the form's two words."""
        for kind in REVIEWS:
            with self.subTest(kind.name):
                text = printed(kind)
                wanted = briefgrade.grade_lines(
                    kind, FORM.approved, FORM.changes_needed
                )
                assert_that(len(wanted) >= 1, equal_to(True))
                for line in wanted:
                    assert_that(text, contains_string(line))
                assert_that(wanted[0].strip().startswith("Plan: "), equal_to(True))

    def test_a_plan_review_has_no_execution_line_and_the_others_have_one(self) -> None:
        """The Plan-only scope prints one line, the rest two."""
        for kind in REVIEWS:
            with self.subTest(kind.name):
                lines = briefgrade.grade_lines(kind, "approved", "changes needed")
                plan_only = kind is brief.Kind.REVIEW_PLAN
                assert_that(len(lines), equal_to(1 if plan_only else 2))

    def test_the_lines_printed_are_ones_the_check_and_the_sweep_read(self) -> None:
        """Filling the verdict with either word gives a line with no finding."""
        for kind in REVIEWS:
            for word in (FORM.approved, FORM.changes_needed):
                with self.subTest(kind.name, word=word):
                    body = "\n".join(
                        each.strip().replace(WORDS, word)
                        for each in briefgrade.grade_lines(
                            kind, FORM.approved, FORM.changes_needed
                        )
                    )
                    found = gradeline.ungraded(body, FORM.approved, FORM.changes_needed)
                    assert_that(list(found), equal_to([]))

    def test_the_form_words_of_the_repository_are_the_words_printed(self) -> None:
        """A repository whose gate says other words gets those words."""
        text = printed(brief.Kind.REVIEW_FULL, verdicts=("ok", "no"))
        assert_that(text, contains_string("Plan: <ok or no>"))
        assert_that(text, contains_string("Execution: <ok or no>"))

    def test_the_fixed_plan_line_is_the_one_the_check_wants(self) -> None:
        """A re-review prints ``fixed_line``, which ``--plan-approved`` wants."""
        text = printed(brief.Kind.REVIEW_EXECUTION)
        assert_that(text, contains_string(gradeline.fixed_line(FORM.approved)))


class TestCheckBeforePosting(unittest.TestCase):
    """Each review brief names the command that checks the comment."""

    def test_the_check_command_exists_and_is_named_in_every_review_brief(self) -> None:
        """``lint review`` is a kind of ``lint``; every review brief says to run it."""
        named_in_every(REVIEWS, [briefgrade.CHECK_COMMAND, f"--head {briefmake.HEAD}"])

    def test_a_gated_repository_check_carries_the_gate_arguments(self) -> None:
        """The gate reads more than the form; the command is told the repository."""
        text = printed(brief.Kind.REVIEW_FULL, gate_note="the gate")
        assert_that(text, contains_string("--gated --repository o/r --config proj"))
        plain = printed(brief.Kind.REVIEW_FULL)
        assert_that(
            "--gated" in plain.split("Check before you post")[1], equal_to(False)
        )

    def test_a_review_of_an_approved_plan_is_checked_with_plan_approved(self) -> None:
        """``--plan-approved`` is named exactly where the fixed Plan line is."""
        for kind in REVIEWS:
            with self.subTest(kind.name):
                fixed = gradeline.fixed_line(FORM.approved) in printed(kind)
                named = "--plan-approved" in printed(kind)
                assert_that(named, equal_to(fixed))


class TestOtherForms(unittest.TestCase):
    """The forms workers write and the ruling, from the constants their checks use."""

    def test_the_review_form_lines_are_in_every_review_brief(self) -> None:
        """Reviewed and Verdict, as ``review-form`` prints them."""
        named_in_every(REVIEWS, [f"Reviewed: {briefmake.HEAD}", f"Verdict: {WORDS}"])

    def test_every_worker_brief_names_the_plan_check_and_the_hand_back_check(
        self,
    ) -> None:
        """The comment `Plan check: ok` and ``hand-back-check`` are named."""
        named_in_every(
            WORKERS, [steps.PLAN_CHECK_OK, "uvx pitboss hand-back-check FILE"]
        )

    def test_a_plan_writing_brief_names_head_evidence_footer_and_the_lint(self) -> None:
        """The body forms: ``Head: <40 hex>``, Evidence by expand, the footer, lint."""
        named_in_every(
            PLAN_AND_BODY,
            ["Evidence", "pitboss expand", "_Generated by", "uvx pitboss lint pr-body"],
        )
        assert_that(printed(brief.Kind.NEW_PR), contains_string("Head: <40 hex>"))

    def test_the_ruling_brief_prints_every_word_and_the_command_that_checks_it(
        self,
    ) -> None:
        """Each word of ``rulingwords.Ruling`` and the ``ruling post`` command."""
        text = printed(brief.Kind.RULING)
        for ruling in rulingwords.Ruling:
            assert_that(text, contains_string(f"`{ruling.value}`"))
        assert_that(text, contains_string("uvx pitboss ruling post"))
        assert_that(text, contains_string("exactly `Opus ruling`"))
