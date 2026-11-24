"""Every wait names the input whose re-read ends it (keyword: idle-event, #524)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import draftfacts, flowstate, idlewait, steps, world

# the field of what pitboss reads on every run that each input is
READ_AS = {
    idlewait.Source.CHECK_RUNS: (flowstate.PullState, "checks"),
    idlewait.Source.RUNNER_QUEUE: (draftfacts.Draft, "hold"),
    idlewait.Source.BLOCKERS: (world.PullRecord, "blocked_by"),
    idlewait.Source.CLOCK: (flowstate.PullState, "undraft_clear"),
    idlewait.Source.SHARED_GROUPS: (world.PullRecord, "shared"),
}


class TestIdleWait(unittest.TestCase):
    """What a PR that no actor takes waits on."""

    def test_each_wait_has_an_input_and_each_input_ends_a_wait(self) -> None:
        """The map is onto both ways: no wait without an input, no orphan input."""
        found = {idlewait.source_of(each) for each in steps.Idle}
        assert_that(found, equal_to(set(idlewait.Source)))

    def test_each_input_is_a_field_of_what_is_read(self) -> None:
        """The input a wait names is one the record or the state holds."""
        missing = [
            source.name
            for source, (kind, name) in READ_AS.items()
            if name not in {each.name for each in dataclasses.fields(kind)}
        ]
        assert_that(missing, equal_to([]))

    def test_ended_is_the_only_move_with_no_wait(self) -> None:
        """An idle PR waits on an event; the ended one is the move with none."""
        moves = [*steps.Idle, *steps.Ended]
        waits = [each for each in moves if isinstance(each, steps.Idle)]
        none = [each for each in moves if each not in waits]
        assert_that(none, equal_to([steps.Ended.IMPOSSIBLE]))
