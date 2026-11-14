"""A runner-pressure hold covers pushes, merges, undrafts and dispatches (B20, T141).

The hold is the owner's rule for the organisation whose runners are busy
(keyword: hold-scope): each clause of B20 and of T141 has a test here whose name
carries the row id, and each has a control with no hold that shows the action.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import holdscope
from . import decisionline, quietworld, test_quiet, world
from .actreviewed import TO_REVIEW
from .exemptworld import copy_pulls, push, with_pitboss
from .pushworld import remote_to
from .exemptworld import runners_in, swept
from .itemworld import one
from .test_flow_sweep import EXECUTION_APPROVED, TWO_PLAN_REJECTIONS
from .test_flow_sweep import approved_draft, world_with
from .test_slot_commands import next_output

THIRD = "owner/project#3"


def merge_world() -> world.World:
    """A world whose PR 3 is approved and green, with a job waiting.

    Returns:
        The world.
    """
    return world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED])


class TestB20(unittest.TestCase):
    """The hold covers each action it names."""

    def test_b20_a_merge_is_withheld_during_a_hold(self) -> None:
        """The held merge is in no answer; with no hold it is the gate's decision."""
        held, clear = merge_world(), quietworld.unheld(merge_world())
        found = [decisionline.of(next_output(each), THIRD) for each in (held, clear)]
        assert_that(found[0], equal_to(""))
        assert_that(found[1], contains_string(TO_REVIEW))

    def test_b20_an_undraft_is_withheld_during_a_hold(self) -> None:
        """The held undraft is in no answer; with no hold it is the gate's decision."""
        held = next_output(with_pitboss(approved_draft()))
        clear = next_output(quietworld.unheld(with_pitboss(approved_draft())))
        assert_that(decisionline.of(held, THIRD), equal_to(""))
        assert_that(decisionline.of(clear, THIRD), contains_string(TO_REVIEW))

    def test_b20_a_push_is_held_and_a_draft_push_is_not(self) -> None:
        """A push goes out only after the quiet period; the control goes out."""
        here = test_quiet.waiting_world(1)
        remote_to(here, "other", "git@github.com:owner/other.git")
        refused = push(here, "other", "branch-1")
        assert_that((refused.code, test_quiet.pushes(here)), equal_to((1, 0)))
        quiet = quietworld.unheld(here)
        sent = push(quiet, "other", "branch-1")
        assert_that((sent.code, test_quiet.pushes(quiet)), equal_to((0, 1)))

    def test_b20_quire_is_spaced_by_15_minutes(self) -> None:
        """The quiet period is 15 minutes: 14 after a hold refuses, 15 allows."""
        here = test_quiet.clear_world()
        test_quiet.write(here, test_quiet.hold_at(0))
        refuses = test_quiet.exit_code(here, "pressure", 14)
        allows = test_quiet.exit_code(here, "pressure", 15)
        assert_that([refuses, allows], equal_to([1, 0]))
        assert_that(runners_in(here).quiet_minutes, equal_to(15))


def other_organisation() -> world.World:
    """A held world with a draft in a repository of another organisation.

    Returns:
        The world; the runners are owner's, a job waits, and the draft of
        ``elsewhere/lib`` is in the same state as the project's.
    """
    here = with_pitboss(approved_draft())
    quietworld.edit_config(
        here, '"dev-skill-up/pitboss"]', '"dev-skill-up/pitboss", "elsewhere/lib"]'
    )
    quietworld.edit_config(
        here, "[runners]", '[runners]\nrepositories = ["owner/project", "owner/lib"]'
    )
    return copy_pulls(here, "elsewhere/lib")


class TestT141(unittest.TestCase):
    """The hold covers the organisation whose runners are busy only."""

    def test_t141_the_pressure_line_names_the_organisation(self) -> None:
        """The pressure line and the sweep say whose runners, and the scope."""
        here = other_organisation()
        line = world.again(here, "pressure", "--now", test_quiet.at(0)).out
        assert_that(line, contains_string("the hold covers only repositories of owner"))
        runners = runners_in(here)
        assert_that(swept(here), contains_string(holdscope.saying(runners)))
        for slug, held in (("owner/lib", True), ("elsewhere/lib", False), (None, True)):
            with self.subTest(slug):
                assert_that(holdscope.applies(runners, slug), equal_to(held))
        assert_that(holdscope.applies(runners, "x/y"), equal_to(False))
        assert_that(holdscope.organisations(runners), equal_to(["owner"]))

    def test_t141_a_repository_of_another_organisation_is_not_held(self) -> None:
        """Its PR has its decision; the project's, held, is in no answer."""
        other = one(other_organisation(), "elsewhere/lib#3").out
        own = one(other_organisation(), THIRD).out
        assert_that(other, contains_string("REVIEWER: elsewhere/lib#3: "))
        assert_that(f": {THIRD}:" in own, equal_to(False))

    def test_t141_a_push_to_another_organisation_goes_out(self) -> None:
        """Pressure on owner's runners holds owner's pushes and not elsewhere's."""
        here = other_organisation()
        remote_to(here, "elsewhere", "git@github.com:elsewhere/lib.git")
        remote_to(here, "ours", "git@github.com:owner/other.git")
        sent, held = (push(here, name, "branch-1") for name in ("elsewhere", "ours"))
        said = "not held" in sent.out
        assert_that([sent.code, held.code, said], equal_to([0, 1, True]))
