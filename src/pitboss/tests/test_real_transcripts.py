"""``slots watch`` over real transcripts (pitboss#415).

The files of ``realtranscripts`` hold the first record and the last three of five
agents of a real session, copied as the session wrote them: a ruling agent and a
reviewer that handed back, a worker that ended its turn, one that was interrupted
and one that was mid-turn.
"""

import datetime
import enum
import unittest

from hamcrest import assert_that, equal_to

from .. import agenttranscript
from . import transcripts, watchworld
from .test_owner_repositories import lines_of as printed

State = agenttranscript.State


class Real(enum.Enum):
    """The agents of the copied transcripts.

    Attributes:
        RULING: an Opus ruling agent that handed back.
        REVIEWER: a reviewer that handed back.
        WORKER: a worker that ended its turn with a plain message.
        STOPPED: an agent that was interrupted.
        Real.MID_TURN.value: an agent whose last record is a tool result.
    """

    RULING = "a2ef207d1166a873c"
    REVIEWER = "a1bd5e47851999369"
    WORKER = "a82dee5f1d8949f3f"
    STOPPED = "a7ce04219a1e9baaf"
    MID_TURN = "a8cdaf6325d11f469"


BEFORE = "2026-11-01T00:00:00+00:00"
AFTER = "2026-11-11T00:00:00+00:00"
ENDINGS = {
    Real.RULING: (State.HANDED_BACK, "handback"),
    Real.REVIEWER: (State.HANDED_BACK, "handback"),
    Real.WORKER: (State.ENDED, "handback"),
    Real.STOPPED: (State.STOPPED, "stopped"),
}
FREED = "LEDGER CHANGED: slot tiny freed from {agent} (owner/project#9): {why}"


def state_of(agent: Real, started: str | None) -> State | None:
    """The state a real transcript reads as.

    Args:
        agent: the agent.
        started: when the Claude process started, ISO 8601, or None.

    Returns:
        Its state.
    """
    when = started and datetime.datetime.fromisoformat(started)
    found = agenttranscript.read(transcripts.REAL / f"{agent.value}.output", when)
    return found.state if found else None


class TestRealStates(unittest.TestCase):
    """The state each real ending reads as."""

    def test_each_real_ending(self) -> None:
        """Hand-back (a worker's and a reviewer's), end of turn, interruption."""
        found = {agent: state_of(agent, BEFORE) for agent in ENDINGS}
        assert_that(found, equal_to({each: pair[0] for each, pair in ENDINGS.items()}))

    def test_a_real_mid_turn_agent_runs_or_is_dead_by_the_process_start(self) -> None:
        """Written after the process started: running, however quiet; before: dead."""
        found = [state_of(Real.MID_TURN, each) for each in (None, BEFORE, AFTER)]
        assert_that(found, equal_to([State.RUNNING, State.RUNNING, State.DEAD]))

    def test_a_brief_that_names_the_hand_back_tool_is_not_a_finish(self) -> None:
        """The real mid-turn agent, its brief now naming SubagentHandback."""
        first, *rest = transcripts.real(Real.MID_TURN.value)
        said = {"role": "user", "content": "call SubagentHandback when done\n"}
        records = [{**first, "message": said}, *rest]
        made = watchworld.play(
            {Real.MID_TURN.value: records},
            rows=[("tiny", Real.MID_TURN.value, "#9")],
            clock=watchworld.Clock(start=BEFORE),
        )
        assert_that(made.held, equal_to([Real.MID_TURN.value]))


class TestRealRows(unittest.TestCase):
    """What the watcher does with a row of a real agent."""

    def test_a_row_is_freed_for_each_real_ending(self) -> None:
        """Handed back, ended and interrupted rows are freed with their reason."""
        for agent, (_, why) in ENDINGS.items():
            with self.subTest(agent):
                made = watchworld.play(
                    {agent.value: transcripts.real(agent.value)},
                    rows=[("tiny", agent.value, "#9")],
                    clock=watchworld.Clock(start=BEFORE),
                )
                said = printed(made.out, "LEDGER CHANGED")
                assert_that(
                    (made.held, said),
                    equal_to(([], [FREED.format(agent=agent.value, why=why)])),
                )

    def test_a_mid_turn_row_stays_unless_the_process_started_after_it(self) -> None:
        """The same real agent: running after one start, dead after the other."""
        found = []
        for start in (BEFORE, AFTER):
            made = watchworld.play(
                {Real.MID_TURN.value: transcripts.real(Real.MID_TURN.value)},
                rows=[("tiny", Real.MID_TURN.value, "#9")],
                clock=watchworld.Clock(start=start),
            )
            found.append((made.held, printed(made.out, "LEDGER CHANGED")))
        assert_that(
            found,
            equal_to(
                [
                    ([Real.MID_TURN.value], []),
                    (
                        [],
                        [
                            FREED.format(
                                agent=Real.MID_TURN.value, why="session restarted"
                            )
                        ],
                    ),
                ]
            ),
        )

    def test_a_real_brief_without_a_marker_is_unmarked_and_holds_no_slot(self) -> None:
        """The real running agent has no PITBOSS-SLOT or Goal line."""
        made = watchworld.play(
            {Real.MID_TURN.value: transcripts.real(Real.MID_TURN.value)},
            rounds="2",
            clock=watchworld.Clock(start=BEFORE),
        )
        said = printed(made.out, "UNMARKED")
        assert_that((made.held, len(said)), equal_to(([], 1)))
