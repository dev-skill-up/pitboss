"""A red CI with a Blocked-by is a step of its own (keyword: one-path, quire#1127)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import blockedstep, steps
from .redfacts import red_pull

OPEN = blockedstep.Blocker(
    reference="o/r#1125", state=blockedstep.State.OPEN, merged_at="", body=""
)
MERGED = dataclasses.replace(
    OPEN, state=blockedstep.State.MERGED, merged_at="2026-11-24T05:00:00Z"
)
BEFORE = "2026-11-24T04:00:00Z"
AFTER = "2026-11-24T06:00:00Z"


class TestRedCi(unittest.TestCase):
    """What a Blocked-by does to a PR whose CI is red."""

    def test_each_blocker_state_gives_its_step(self) -> None:
        """Open: held. Merged after the red: fixed after it. Else its own."""
        found: list[steps.Move | None] = [
            blockedstep.verdict(red_pull(ended=BEFORE), [OPEN]),
            blockedstep.verdict(red_pull(ended=BEFORE), [MERGED]),
            blockedstep.verdict(red_pull(ended=AFTER), [MERGED]),
        ]
        assert_that(
            found,
            equal_to(
                [steps.Idle.BLOCKER_OPEN, steps.worker(steps.Task.AFTER_BLOCKER), None]
            ),
        )
