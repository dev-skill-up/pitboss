"""A FIX_CI brief carries what each failed check said (keyword: failure-text, #524)."""

from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to
import unittest

from .. import brief, pulls, suggestfailed
from . import fakes
from .briefmake import text
from .redfacts import red_pull

CASE = "repos/o/r/check-runs/9"
ANSWERS: Mapping[str, object] = {
    CASE: {"output": {"title": "", "summary": ""}},
    CASE
    + "/annotations?per_page=20": [
        {
            "path": ".github",
            "start_line": 4,
            "message": "bats.lock differs",
            "annotation_level": "failure",
        }
    ],
    "repos/o/r/actions/jobs/9": {"steps": [{"name": "Check", "conclusion": "failure"}]},
}


def said(
    failed: bool = True,
    kind: brief.Kind = brief.Kind.FIX_CI,
    pull: pulls.PullFacts | None = None,
) -> Sequence[str]:
    """What the brief says of one check of a PR, named like quire#1127's.

    Args:
        failed: whether the check failed.
        kind: the kind of brief.
        pull: the PR; the red one when none is given.

    Returns:
        The lines.
    """
    return suggestfailed.of(fakes.github(dict(ANSWERS)), pull or red_pull(failed), kind)


class TestFailureText(unittest.TestCase):
    """The text of each failed run reaches the brief."""

    def test_a_failed_check_is_said_with_its_annotation(self) -> None:
        """The quire#1127 shape: a failed check with annotations and no title."""
        found = " ".join(said())
        assert_that(found, contains_string("'canonical-files'"))
        assert_that(found, contains_string("failed step 'Check'"))
        assert_that(found, contains_string("bats.lock differs"))
        assert_that(said(False), equal_to([]))

    def test_no_other_brief_and_no_ticket_names_a_failure(self) -> None:
        """Only a FIX_CI brief of a PR carries the lines."""
        assert_that(said(kind=brief.Kind.REVIEW_FULL), equal_to([]))
        hub = fakes.github(dict(ANSWERS))
        assert_that(suggestfailed.of(hub, None, brief.Kind.FIX_CI), equal_to([]))

    def test_the_brief_names_what_failed(self) -> None:
        """A FIX_CI brief has the lines."""
        assert_that(
            text(brief.Kind.FIX_CI, failed=said()),
            contains_string("bats.lock differs"),
        )
