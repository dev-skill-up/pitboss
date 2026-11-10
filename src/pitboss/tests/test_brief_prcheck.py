"""The Execution review briefs tell the reviewer to run the checklist (#438)."""

import unittest

from hamcrest import assert_that, contains_string

from .. import brief
from .briefmake import has_none, text

REPOSITORIES = [
    "bats-lang/bats",
    "bats-lang/quire",
    "bats-lang/bridge",
    "bats-lang/pwa",
    "bats-lang/capacitor-plugins",
]
COMMAND = "bats prcheck --checklist"
EXECUTION_REVIEWS = [brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION]
OTHER_REVIEWS = sorted(brief.REVIEWS - set(EXECUTION_REVIEWS), key=lambda k: k.name)


class TestPrcheckChecklist(unittest.TestCase):
    """The review of a pull request of each repository names the command."""

    def test_the_review_brief_of_each_repository_has_the_command(self) -> None:
        """The brief names the command and the checkout of its repository."""
        for kind in EXECUTION_REVIEWS:
            for repo in REPOSITORIES:
                found = text(kind, repo=repo)
                assert_that(found, contains_string(COMMAND))
                assert_that(found, contains_string(f"checkout of {repo} at the head"))
                assert_that(found, contains_string("`checked, ok`"))

    def test_the_reviews_that_grade_no_execution_do_not_carry_it(self) -> None:
        """A Plan, a resolution, a fix round and a relock review do not."""
        for kind in OTHER_REVIEWS:
            has_none(text(kind), [COMMAND])
