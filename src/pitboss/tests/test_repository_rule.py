"""A hand-back that stops at a repository's rule says where else the feature lives.

Pitboss#437.
"""

import json
import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import relockfix, repositoryrule
from .cleanworld import same
from .handbackrun import hand_back, no_jobs
from .handbackworld import ready
from . import handbackworld
from .says import says
from . import world

STOPPED = (
    "NOT STARTED: pwa's CLAUDE.md allows only bug fixes and new platforms, and the"
    " ticket asks for a feature.\n"
)
PLACE = "Could live in: bats-lang/quire\n"


class TestRepositoryRule(unittest.TestCase):
    """The nearest accepting input is a hand-back that names another place."""

    def test_t437_a_stop_at_a_repository_rule_with_no_other_place_is_refused(
        self,
    ) -> None:
        """Exit 1, and the message quotes the allowance and the two ways out."""
        here = ready(world.make_world())
        refused = hand_back(here, no_jobs(), text=STOPPED)
        same(refused.code, 1)
        says(refused.out, "gives way when that repository is the only place")
        says(refused.out, "2026-11-09 20:52Z")
        says(refused.out, "Could live in: <owner/repo>")

    def test_t437_a_hand_back_that_names_another_place_passes_the_rule(self) -> None:
        """The same hand-back with a place: the rule has nothing to say."""
        _quiet(STOPPED + PLACE, STOPPED + "Ticket in: bats-lang/pwa#9\n")

    def test_t437_a_stop_that_cites_no_rule_is_not_this_refusal(self) -> None:
        """Only a NOT STARTED hand-back that cites a rule is read."""
        _quiet("NOT STARTED: the ticket is closed.\n", "Done. CLAUDE.md allows it.\n")


def _quiet(*texts: str) -> None:
    # the rule has nothing to say of any of the hand-backs
    assert_that(
        [repositoryrule.refusal(each) for each in texts], equal_to([""] * len(texts))
    )


FIX_TABLE = (
    "| run | pages |\n|---|---|\n| [1](https://github.com/o/r/actions/runs/1) | 2.61"
    " |\n| [2](https://github.com/o/r/actions/runs/2) | 6.90 |\n"
)
SECTION = (
    "## Test fix\n\ntests/budget.py changed: the maximum is 6.90 pages and the"
    " margin over it is 1.1, because a run varies.\n\n" + FIX_TABLE
)
PINS = ["bats.lock", ".github/bats-version"]


class TestRelockTestFix(unittest.TestCase):
    """A relock with a test file beside the pins shows its data (pitboss#447)."""

    def test_t447_a_relock_with_a_test_file_and_no_section_is_refused(self) -> None:
        """Each missing part is named."""
        found = relockfix.findings("Moves pins.\n", "", [*PINS, "tests/budget.py"])
        assert_that(found, has_length(4))
        assert_that(found[0], contains_string("a `Test fix` section"))

    def test_t447_a_relock_with_the_section_and_its_data_passes(self) -> None:
        """The control: the section names the file, the runs and the maximum."""
        found = relockfix.findings(SECTION, "", [*PINS, "tests/budget.py"])
        assert_that(found, empty())

    def test_t447_a_relock_of_pins_alone_needs_no_section(self) -> None:
        """No test file: nothing is asked."""
        assert_that(relockfix.findings("Moves pins.\n", "", PINS), empty())

    def test_t447_figures_the_comment_quotes_are_the_tables_minimum_and_maximum(
        self,
    ) -> None:
        """3.6 to 6.7 against the table's 2.61 to 6.90 is refused (quire PR 1101)."""
        names = [*PINS, "tests/budget.py"]
        wrong = relockfix.findings(SECTION, "Test fix: 3.6 to 6.7 pages", names)
        assert_that(wrong, has_length(1))
        assert_that(wrong[0], contains_string("2.61 to 6.9"))
        right = relockfix.findings(SECTION, "Test fix: 2.61 to 6.90 pages", names)
        assert_that(right, empty())

    def test_t447_hand_back_check_reads_the_relock_pr(self) -> None:
        """The hand-back of a relock PR whose diff has a test file is refused."""
        here = world.make_world()
        handbackworld.git(here.clone, "checkout", "-q", "-b", "relock/2026-11-12")
        here = handbackworld.ready(here)
        files = [{"filename": "bats.lock"}, {"filename": "tests/budget.py"}]
        here.bodies[f"{handbackworld.BASE}/pulls/7/files?per_page=100&page=1"] = (
            json.dumps(files)
        )
        refused = hand_back(here, no_jobs())
        same(refused.code, 1)
        says(refused.out, "lacks a `Test fix` section (relock-test-fix)")
