"""Actions check the step, then write."""

import unittest

from hamcrest import assert_that, equal_to

from .. import actions, machine
from . import world

READY = world.READY


class TestRun(unittest.TestCase):
    """``actions.run``."""

    def test_refused_writes_nothing(self) -> None:
        """A PR not at the verb's step is refused."""
        hub = world.Fake()
        out = actions.run(actions.Ask(verb="merge"), hub, world.pull(), machine.Gates())
        want = actions.Refused(
            wanted={machine.Step.MERGE}, found=machine.Step.PLAN_CHECK
        )
        assert_that(out, equal_to(want))
        assert_that(hub.seen(), equal_to([]))

    def test_each_verb(self) -> None:
        """Each verb writes once when its step stands."""
        cases = [
            ("merge", "", "success", ""),
            ("undraft", "draft", "success", ""),
            ("update-branch", "dirty", "success", ""),
            ("rerun", "", "failure", ""),
            ("dispatch", "draft", "success", "e2e/a"),
            ("close", "", "success", ""),
            ("label", "", "success", ""),
            ("comment", "", "success", ""),
        ]
        for verb, tags, run, path in cases:
            pr = world.pull(tags, (run,), READY, [path] if path else [])
            hub = world.Fake()
            ask = actions.Ask(verb=verb, text="t")
            out = actions.run(ask, hub, pr, machine.Gates())
            assert_that(out, equal_to(actions.Done(verb=verb)))
            assert_that(hub.seen(), equal_to([(verb, 7)]))

    def test_held_merge_is_refused(self) -> None:
        """A hold turns the merge step into HELD, so the merge is refused."""
        ask = actions.Ask(verb="merge")
        out = actions.run(
            ask, world.Fake(), world.pull(comments=READY), machine.Gates(hold=True)
        )
        assert_that(
            out,
            equal_to(
                actions.Refused(wanted={machine.Step.MERGE}, found=machine.Step.HELD)
            ),
        )
