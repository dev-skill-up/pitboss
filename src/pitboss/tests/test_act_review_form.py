"""``act review`` writes the lines the repository's reviews take (act-review-form)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import actport, actreview, actwrite, gradesrequired

HEAD = "a" * 40
BASE = (
    f"Reviewed: {HEAD}\nPlan: approved\nExecution: approved\nVerdict: approved\nBody: 1"
)
ONE_LINE = ["Independent review of head {sha}: {verdict}"]
GATED = ["## Adversarial review", "Reviewed: {sha}", "Verdict: {verdict}"]


class TestFormed(unittest.TestCase):
    """The form's lines come first and the review's own head and verdict go."""

    def test_no_form_leaves_the_review_as_written(self) -> None:
        """A repository whose form is not read keeps the review as it was."""
        assert_that(actwrite.formed(BASE, [], HEAD, "approved"), equal_to(BASE))

    def test_a_one_line_form_opens_the_review(self) -> None:
        """The head and the verdict are in the form's line only."""
        found = actwrite.formed(BASE, ONE_LINE, HEAD, "approved").splitlines()
        assert_that(
            found,
            equal_to(
                [
                    f"Independent review of head {HEAD}: approved",
                    "Plan: approved",
                    "Execution: approved",
                    "Body: 1",
                ]
            ),
        )

    def test_a_gated_form_has_its_own_head_and_verdict_lines_once(self) -> None:
        """The gate's lines are written once, not twice."""
        found = actwrite.formed(BASE, GATED, HEAD, "approved").splitlines()
        assert_that(
            found[:3],
            equal_to(
                ["## Adversarial review", f"Reviewed: {HEAD}", "Verdict: approved"]
            ),
        )
        assert_that(found.count(f"Reviewed: {HEAD}"), equal_to(1))


WORDS = (
    f"Reviewed: {HEAD}\nPlan: approved\nExecution: changes needed\n"
    "Verdict: changes needed\nBody: 1\nPlan-digest: 2\n\nfindings"
)


class TestKinds(unittest.TestCase):
    """A review has the lines of its kind and the digests of the body read."""

    def test_the_kinds_are_the_ones_lint_review_takes(self) -> None:
        """The kinds act review writes are the `--review-kind` words."""
        assert_that(actreview.KINDS, equal_to(tuple(gradesrequired.REQUIRED)))

    def test_a_plan_review_has_no_execution_line(self) -> None:
        """The Plan alone is graded."""
        found = actreview.shaped(WORDS, "plan", {})
        assert_that("Execution:" in found, equal_to(False))
        assert_that("Plan: approved\n" in found, equal_to(True))

    def test_a_review_after_the_plan_was_approved_has_the_fixed_plan_line(self) -> None:
        """An Execution, resolution, fix-round and relock review fix the Plan."""
        for kind in ("execution", "resolution", "fix-round", "relock"):
            found = actreview.shaped(WORDS, kind, {})
            assert_that("Plan: approved (fixed)\n" in found, equal_to(True))
            assert_that("Execution: changes needed" in found, equal_to(True))

    def test_the_digests_are_the_ones_given(self) -> None:
        """The body and the Plan digest the reviewer read replace the live ones."""
        options = {"body": "aaaa", "plan-digest": "bbbb"}
        found = actreview.shaped(WORDS, "full", options).splitlines()
        assert_that(found[4:6], equal_to(["Body: aaaa", "Plan-digest: bbbb"]))

    def test_a_grade_the_kind_does_not_write_is_not_asked_for(self) -> None:
        """A Plan review gives no execution grade, an Execution review no plan."""
        both = {"plan": "approved", "execution": "approved", "verdict": "approved"}
        plan = {"plan": "approved", "verdict": "approved"}
        execution = {"execution": "approved", "verdict": "approved"}
        assert_that(actreview.grades_of("plan", plan)[0], equal_to("approved"))
        assert_that(
            actreview.grades_of("execution", execution)[1], equal_to("approved")
        )
        assert_that(len(actreview.grades_of("full", both)), equal_to(3))

    def test_a_kind_no_review_has_is_refused(self) -> None:
        """Only the `--review-kind` words are kinds."""
        with self.assertRaises(actport.Refused):
            actreview.kind_of({"kind": "other"})
        assert_that(actreview.kind_of({}), equal_to("full"))
