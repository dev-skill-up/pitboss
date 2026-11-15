"""A review brief holds what only a reviewer can do (keyword: reviewer-only)."""

import unittest

from . import briefmake
from .briefmake import text
from .says import has_all, has_none
from .. import (
    brief,
    briefgrade,
    brieftextci,
    brieftextexec,
    brieftextfailure,
    brieftextlint,
)
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

    def test_every_review_is_posted_by_act_review_with_its_kind_and_digest(
        self,
    ) -> None:
        """The brief names `act review`, the kind word and the body digest read."""
        for kind in brief.REVIEWS:
            found = text(kind)
            word = briefgrade.KIND_WORDS[kind]
            has_all(found, ["uvx pitboss act review o/r#3", f"kind={word}"])
            has_all(found, [f"body={briefmake.BODY_DIGEST}"])
            has_none(found, ["Form:", "Grade lines:", "Body: the PR body"])

    def test_the_grades_asked_for_are_the_ones_the_kind_needs(self) -> None:
        """A Plan review gives the Plan, a review after the Plan the Execution."""
        plan = text(Kind.REVIEW_PLAN)
        has_all(plan, ["plan=<approved", f"plan-digest={briefmake.PLAN_DIGEST}"])
        has_none(plan, ["execution="])
        for kind in (Kind.REVIEW_EXECUTION, Kind.REVIEW_RELOCK):
            has_all(text(kind), ["execution=<approved"])
            has_none(text(kind), ["plan=", "plan-digest="])
        has_all(text(Kind.REVIEW_FULL), ["plan=<approved", "execution=<approved"])
