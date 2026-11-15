"""``act review`` writes the lines the repository's reviews take (act-review-form)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import actwrite

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
