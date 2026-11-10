"""``slots watch`` over real transcripts (pitboss#415).

The files of ``realtranscripts`` hold the first record and the last three of five
agents of a real session, copied as the session wrote them: a ruling agent and a
reviewer that handed back, a worker that ended its turn, one that was interrupted
and one that was mid-turn.
"""

import datetime
import enum
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to, has_length

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
        MID_TURN: an agent whose last record is a tool result.
    """

    RULING = enum.auto()
    REVIEWER = enum.auto()
    WORKER = enum.auto()
    STOPPED = enum.auto()
    MID_TURN = enum.auto()


IDS = {
    Real.RULING: "a2ef207d1166a873c",
    Real.REVIEWER: "a1bd5e47851999369",
    Real.WORKER: "a82dee5f1d8949f3f",
    Real.STOPPED: "a7ce04219a1e9baaf",
    Real.MID_TURN: "a8cdaf6325d11f469",
}
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
    when = datetime.datetime.fromisoformat(started) if started else None
    found = agenttranscript.read(transcripts.REAL / f"{IDS[agent]}.output", when)
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
        first, *rest = real_mid()
        said = {"role": "user", "content": "call SubagentHandback when done\n"}
        records = [{**first, "message": said}, *rest]
        rows = [("tiny", IDS[Real.MID_TURN], "#9")]
        assert_that(mid_turn(records, rows).held, equal_to([IDS[Real.MID_TURN]]))


def real_mid() -> Sequence[Mapping[str, object]]:
    """The records of the real mid-turn agent.

    Returns:
        Its transcript.
    """
    return transcripts.real(IDS[Real.MID_TURN])


def mid_turn(
    records: Sequence[Mapping[str, object]],
    rows: Sequence[tuple[str, str, str]],
    rounds: str = "1",
) -> watchworld.Left:
    """Watch the real mid-turn agent with these records, its process older.

    Args:
        records: the records of its transcript.
        rows: the ledger rows.
        rounds: how many polls.

    Returns:
        What the watcher did.
    """
    return watchworld.play(
        {IDS[Real.MID_TURN]: records},
        rows=rows,
        rounds=rounds,
        clock=watchworld.Clock(start=BEFORE),
    )


def row_of(agent: Real, start: str) -> tuple[Sequence[str], Sequence[str]]:
    """What the watcher holds and says for a row of a real agent.

    Args:
        agent: the agent the row names.
        start: when the Claude process started, ISO 8601.

    Returns:
        The agents still held and the LEDGER CHANGED lines.
    """
    made = watchworld.play(
        {IDS[agent]: transcripts.real(IDS[agent])},
        rows=[("tiny", IDS[agent], "#9")],
        clock=watchworld.Clock(start=start),
    )
    return made.held, printed(made.out, "LEDGER CHANGED")


class TestRealRows(unittest.TestCase):
    """What the watcher does with a row of a real agent."""

    def test_a_row_is_freed_for_each_real_ending(self) -> None:
        """Handed back, ended and interrupted rows are freed with their reason."""
        found = {each: row_of(each, BEFORE) for each in ENDINGS}
        said: Mapping[Real, tuple[Sequence[str], Sequence[str]]] = {
            each: ([], [FREED.format(agent=IDS[each], why=pair[1])])
            for each, pair in ENDINGS.items()
        }
        assert_that(found, equal_to(said))

    def test_a_mid_turn_row_stays_unless_the_process_started_after_it(self) -> None:
        """The same real agent: running after one start, dead after the other."""
        found = [row_of(Real.MID_TURN, each) for each in (BEFORE, AFTER)]
        why = FREED.format(agent=IDS[Real.MID_TURN], why="session restarted")
        assert_that(found, equal_to([([IDS[Real.MID_TURN]], []), ([], [why])]))

    def test_a_real_brief_without_a_marker_is_unmarked_and_holds_no_slot(self) -> None:
        """The real running agent has no PITBOSS-SLOT or Goal line."""
        made = mid_turn(real_mid(), [], "2")
        assert_that(made.held, equal_to([]))
        assert_that(printed(made.out, "UNMARKED"), has_length(1))
