"""A review brief holds what only a reviewer can do (keyword: reviewer-only)."""

import unittest

from .briefmake import text
from .says import has_all, has_none
from .. import brief, brieftextci, brieftextexec, brieftextfailure, brieftextlint
from .. import brieftextnote, brieftextorder
from ..brief import Kind
from .. import brieftext

CUT = [
    brieftext.CHECK,
    brieftext.GREP,
    brieftext.PLAN_COMMANDS_PLAN,
    brieftext.PLAN_DRY_RUN,
    brieftextci.QUARANTINE_REVIEW,
    brieftextci.PLAN_CHECK,
    brieftextci.REVIEW_CI_ACCEPTED,
    *brieftextci.PLAN_CI_REVIEW,
    brieftextexec.PLAN_COMMANDS_EXECUTION,
    brieftextnote.DEVIATIONS_REVIEW,
    brieftextlint.LINT_TEST_REVIEW,
    brieftextorder.ORDER_REVIEW,
    brieftextfailure.FAILURE_REVIEW,
]


class TestReviewerOnly(unittest.TestCase):
    """What pitboss checks in code, or a worker shows, is not in the brief."""

    def test_no_review_brief_carries_a_check_that_pitboss_or_a_worker_makes(
        self,
    ) -> None:
        """Head line, evidence, Plan commands, Plan check and the like are cut."""
        for kind in brief.REVIEWS:
            has_none(text(kind), CUT)

    def test_a_full_review_still_names_its_scope_and_its_notes(self) -> None:
        """The scope, the notes rule and the design check stay."""
        has_all(
            text(Kind.REVIEW_FULL),
            [brieftext.SCOPE_FULL.split("{")[0], brieftextnote.REVIEW_NOTES],
        )

    def test_a_review_that_grades_an_execution_is_posted_by_act_review(self) -> None:
        """The brief names `act review` and leaves out the form and the digests."""
        for kind in (Kind.REVIEW_FULL, Kind.REVIEW_EXECUTION):
            found = text(kind)
            has_all(found, ["uvx pitboss act review o/r#3"])
            has_none(found, ["Form:", "Grade lines:", "Body: the PR body"])

    def test_the_other_reviews_still_carry_the_form(self) -> None:
        """A Plan review and a scoped review post a comment of their own form."""
        for kind in (Kind.REVIEW_PLAN, Kind.REVIEW_RESOLUTION, Kind.REVIEW_FIX_ROUND):
            has_all(text(kind), ["Form:"])
            has_none(text(kind), ["act review"])
