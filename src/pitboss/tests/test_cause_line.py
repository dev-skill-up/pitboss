"""A red check prints its log and the rule on its cause (pitboss#420)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief, causeline, causetext, shapes
from . import syncworld, world
from .briefmake import has_none, pinned, text
from .test_commands import OPEN_PULLS, sweep

SENTENCE = (
    "the answer to a red check is its cause: either the log names it (the step,"
    " the line) or the next change is the trace or state capture that would show"
    " it (a ticket or a change of its own); a push or a re-run whose only purpose"
    " is a new run is refused"
)
LINE = (
    "RED CAUSE owner/project#1: test: log https://github.com/owner/project/runs/8; "
    + SENTENCE
)


class TestCauseLine(unittest.TestCase):
    """The sweep's RED CAUSE line."""

    def test_the_rule_is_pinned(self) -> None:
        """The rule's words are the ones the ticket asks for."""
        assert_that(causetext.RULE, equal_to(SENTENCE))

    def test_a_red_check_prints_its_log_and_the_rule(self) -> None:
        """A failed check gets a RED CAUSE line naming its log."""
        lines = sweep(world.make_world()).out.splitlines()
        assert_that(LINE in lines, equal_to(True))

    def test_an_actions_check_names_its_job(self) -> None:
        """A check of a workflow run is located by the run and the job."""
        check = shapes.CheckRun(id=8, name="test", finished=True, failed=True, run=5)
        assert_that(
            causeline.log_location("o/r", check),
            equal_to("https://github.com/o/r/actions/runs/5/job/8"),
        )

    def test_a_green_check_prints_none_of_it(self) -> None:
        """A sweep with no red check has no RED CAUSE line."""
        here = syncworld.make_synced().here
        here.bodies[OPEN_PULLS] = [{"number": 2}]
        out = sweep(here).out
        assert_that("RED CAUSE" in out or SENTENCE in out, equal_to(False))


class TestCauseBrief(unittest.TestCase):
    """The brief that fixes a red CI."""

    def test_the_fix_ci_brief_prints_the_rule(self) -> None:
        """FIX_CI states that the cause is the answer."""
        pinned(brief.Kind.FIX_CI, [SENTENCE])

    def test_every_other_brief_leaves_it_out(self) -> None:
        """No other brief prints the rule."""
        for kind in set(brief.Kind) - {brief.Kind.FIX_CI}:
            has_none(text(kind), [SENTENCE])
