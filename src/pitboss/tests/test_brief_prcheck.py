"""The Execution review briefs tell the reviewer to run the checklist (#438)."""

import unittest

from hamcrest import assert_that, contains_string

from .briefmake import text
from .says import has_none
from ..brief import Kind

REPOSITORIES = [
    "bats-lang/bats",
    "bats-lang/quire",
    "bats-lang/bridge",
    "bats-lang/pwa",
    "bats-lang/capacitor-plugins",
]
COMMAND = "bats prcheck --checklist"
CARRIERS = [Kind.REVIEW_FULL, Kind.REVIEW_EXECUTION]
OTHERS = [
    Kind.REVIEW_PLAN,
    Kind.REVIEW_RESOLUTION,
    Kind.REVIEW_FIX_ROUND,
    Kind.REVIEW_RELOCK,
]


class TestPrcheckChecklist(unittest.TestCase):
    """The review of a pull request of each repository names the command."""

    def test_the_review_brief_of_each_repository_has_the_command(self) -> None:
        """The brief names the command and the checkout of its repository."""
        for repo in REPOSITORIES:
            for kind in CARRIERS:
                found = text(kind, repo=repo)
                for wanted in (COMMAND, f"checkout of {repo} at", "`checked, ok`"):
                    assert_that(found, contains_string(wanted))

    def test_the_reviews_that_grade_no_execution_do_not_carry_it(self) -> None:
        """A Plan, a resolution, a fix round and a relock review do not."""
        for kind in OTHERS:
            has_none(text(kind), [COMMAND])
