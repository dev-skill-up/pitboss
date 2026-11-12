"""A runner-pressure hold covers pushes, merges, undrafts and dispatches (B20, T141).

The hold is the owner's rule for the organisation whose runners are busy
(keyword: hold-scope): each clause of B20 and of T141 has a test here whose name
carries the row id, and each has a control with no hold that shows the action.
"""

import functools
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import holdscope
from . import exemptworld, quietworld, test_quiet, world
from .exemptworld import copy_pulls, drafted_pair, of, push, remote_to
from .exemptworld import runners_in, swept
from .test_commands import sweep
from .test_flow_sweep import EXECUTION_APPROVED, TWO_PLAN_REJECTIONS, world_with
from .test_slot_commands import next_output

MERGE = "READY TO MERGE owner/project#3"


def merge_world() -> world.World:
    """A world whose PR 3 is approved and green, with a job waiting.

    Returns:
        The world.
    """
    return world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED])


class TestB20(unittest.TestCase):
    """The hold covers each action it names."""

    def test_b20_a_merge_is_withheld_during_a_hold(self) -> None:
        """No merge line while the hold lasts; the step names the hold; a control."""
        held = merge_world()
        clear = quietworld.unheld(merge_world())
        shown = [MERGE in sweep(each).out for each in (held, clear)]
        assert_that(shown, equal_to([False, True]))
        waiting = exemptworld.state_line(held)
        assert_that(waiting, contains_string(exemptworld.HELD_WORDS))

    def test_b20_an_undraft_is_withheld_during_a_hold(self) -> None:
        """The draft waits for the window; with no hold it is marked ready."""
        held = of(next_output(drafted_pair()), "NEXT", "owner/project#3")[0]
        clear = of(
            next_output(quietworld.unheld(drafted_pair())), "NEXT", "owner/project#3"
        )
        assert_that(held, contains_string("HOLD on undrafts"))
        assert_that("draft=false" in held, equal_to(False))
        assert_that(clear[0], contains_string("draft=false"))

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
    here = drafted_pair()
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
        assert_that(swept(here), contains_string(holdscope.saying(runners_in(here))))

    def test_t141_a_repository_of_another_organisation_is_not_held(self) -> None:
        """Its draft is marked ready and has no wait line; the project's waits."""
        shown = next_output(other_organisation())
        other = of(shown, "NEXT", "elsewhere/lib#3")
        own = of(shown, "NEXT", "owner/project#3")
        assert_that("mark the PR ready" in other[0], equal_to(True))
        assert_that("HOLD" in other[0], equal_to(False))
        assert_that("HOLD on undrafts" in own[0], equal_to(True))

    def test_t141_a_push_to_another_organisation_goes_out(self) -> None:
        """Pressure on owner's runners holds owner's pushes and not elsewhere's."""
        here = other_organisation()
        remote_to(here, "elsewhere", "git@github.com:elsewhere/lib.git")
        remote_to(here, "ours", "git@github.com:owner/other.git")
        sent = push(here, "elsewhere", "branch-1")
        held = push(here, "ours", "branch-1")
        assert_that((sent.code, held.code), equal_to((0, 1)))
        assert_that(sent.out, contains_string("not held"))

    def test_t141_two_organisations_in_one_config(self) -> None:
        """The scope is a property of the configuration: owner's, not elsewhere's."""
        here = other_organisation()
        runners = runners_in(here)
        slugs = ("owner/project", "owner/lib", "elsewhere/lib", "x/y", None)
        found = list(map(functools.partial(holdscope.applies, runners), slugs))
        assert_that(found, equal_to([True, True, False, False, True]))
        assert_that(holdscope.organisations(runners), equal_to(["owner"]))
