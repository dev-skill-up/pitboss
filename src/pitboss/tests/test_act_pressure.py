"""A verb that costs runs refuses while runners are held (keyword: act-pressure).

The queue session sent a workflow dispatch with a raw ``gh api`` while ``pressure``
said HOLD, because no verb read the pressure: it was a rule an agent had to
remember. Now the verb reads it in its one read, and a hold stands in its decision.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import actdecide, actfacts, answer
from . import quietworld, test_quiet, world

SENT = "POST repos/owner/project/actions/workflows/relock.yml/dispatches"
NOON = test_quiet.at(60)
DISPATCH = (
    "act",
    "dispatch-workflow",
    "owner/project",
    "workflow=relock.yml",
    "ref=main",
    "--no-dry-run",
)


def read(verb: str, pressured: str) -> actfacts.ActRead:
    """What a verb is decided from, with the pressure given.

    Args:
        verb: the verb.
        pressured: the pressure line, empty when the runners are free.

    Returns:
        The read.
    """
    return actfacts.ActRead(
        verb=verb, repos=["owner/project"], pending=[], checks=[], pressured=pressured
    )


def decided(verb: str, pressured: str) -> answer.Acting:
    """The verdict of a verb with the pressure given and no hold.

    Args:
        verb: the verb.
        pressured: the pressure line.

    Returns:
        What stands, None when nothing does.
    """
    return actdecide.verdict(read(verb, pressured), {}, actdecide.ROWS)


class TestTheVerdict(unittest.TestCase):
    """The decision."""

    def test_a_verb_that_costs_runs_stands_while_the_runners_are_held(self) -> None:
        """Merge, arm, undraft, rerun and dispatch-workflow."""
        for verb in ("merge", "arm", "undraft", "rerun", "dispatch-workflow"):
            with self.subTest(verb):
                found = decided(verb, "RUNNER PRESSURE: 3 waiting")
                assert found is not None
                assert_that(found.why, equal_to(answer.Why.PRESSURE))

    def test_free_runners_and_the_verbs_that_cost_none_stand_nowhere(self) -> None:
        """No pressure, or a verb a hold never stops."""
        assert_that(decided("dispatch-workflow", ""), equal_to(None))
        assert_that(decided("comment", "RUNNER PRESSURE: 3 waiting"), equal_to(None))


class TestTheCommand(unittest.TestCase):
    """``pitboss act`` reads the pressure itself."""

    def test_the_dispatch_is_refused_and_nothing_is_sent_while_jobs_wait(self) -> None:
        """The failing case of the queue session."""
        here = test_quiet.waiting_world(2)
        done = world.invoke(here, *DISPATCH, "--config", here.config)
        assert_that(done.out + done.err, contains_string("RUNNER PRESSURE"))
        assert_that(sent_to(here), equal_to(0))

    def test_the_dispatch_is_sent_when_nothing_waits(self) -> None:
        """The control: the same command with free runners."""
        assert_that(dispatches_an_hour_after_a_hold(), equal_to(1))

    def test_a_project_with_no_runners_table_is_never_held(self) -> None:
        """No ``[runners]``: no look is made, and the dispatch is sent."""
        here = test_quiet.waiting_world(2)
        quietworld.edit_config(here, "[runners]", "")
        here.bodies[SENT] = ""
        world.invoke(here, *DISPATCH, "--config", here.config, "--now", NOON)
        assert_that(sent_to(here), equal_to(1))


def sent_to(here: world.World) -> int:
    """How many dispatches the world was sent.

    Args:
        here: the world.

    Returns:
        The count.
    """
    return sum(1 for each in here.calls if each[-1].endswith("/dispatches"))


def dispatches_an_hour_after_a_hold() -> int:
    """How many dispatches the command sends an hour after a hold, runners free.

    A first look owes the quiet period, so a hold is on record.

    Returns:
        The count.
    """
    here = test_quiet.clear_world()
    test_quiet.write(here, test_quiet.hold_at(0))
    here.bodies[SENT] = ""
    world.invoke(here, *DISPATCH, "--config", here.config, "--now", NOON)
    return sent_to(here)
