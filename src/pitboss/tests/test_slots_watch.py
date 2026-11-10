"""``slots watch`` keeps the ledger from the agents' transcripts (pitboss#415)."""

import unittest
from typing import Sequence

from hamcrest import (
    assert_that,
    equal_to,
    starts_with,
)

from .. import agenttranscript
from . import watchworld, world
from .test_owner_repositories import lines_of as printed
from .test_handback import slots
from .transcripts import brief, call, ended, interrupted, turn_end
from .watchworld import FREED, GOAL, MARKED, OLD, QUIET, RECENT

EARLIER = watchworld.LONG_AGO
Records = watchworld.Records

ROW = ("tiny", "a1", "#9")
BRIEF = brief("a1", GOAL.format(n=9), EARLIER)
HANDED = [BRIEF, call("SubagentHandback", EARLIER), turn_end(EARLIER)]
RESUMED = [*HANDED, brief("a1", "go on", RECENT)]
CASES: Sequence[tuple[str, Records, Sequence[str], Sequence[str]]] = [
    # the name, the records, the agents held after, the lines
    ("handed back", HANDED, [], [FREED.format("handback")]),
    ("ended its turn", [BRIEF, ended(EARLIER)], [], [FREED.format("handback")]),
    ("interrupted", [BRIEF, interrupted(RECENT)], [], [FREED.format("stopped")]),
    ("resumed, mid-turn", RESUMED, ["a1"], []),
    ("resumed, answered", [*RESUMED, ended(RECENT)], [], [FREED.format("handback")]),
    ("quiet since the start", [BRIEF, call("Bash", QUIET)], ["a1"], []),
    ("dead", [BRIEF, call("Bash", OLD)], [], [FREED.format("session restarted")]),
]


def changed(out: str) -> Sequence[str]:
    """The ``LEDGER CHANGED`` lines of an output.

    Args:
        out: what the watcher printed.

    Returns:
        The lines.
    """
    return printed(out, "LEDGER CHANGED")


def worker(agent: str, number: int) -> Records:
    """The transcript of a running worker on a ticket.

    Args:
        agent: its id.
        number: the ticket's number.

    Returns:
        The records.
    """
    return [brief(agent, GOAL.format(n=number), RECENT), call("Bash", RECENT)]


NEEDS = "needs [slots] agents-dir in the configuration\n"


class TestWatch(unittest.TestCase):
    """What a round writes and prints."""

    def test_the_state_of_each_ending(self) -> None:
        """Hand-back, end of turn, interruption, resume, quiet and dead."""
        for name, records, after, lines in CASES:
            with self.subTest(name):
                made = watchworld.play({"a1": records}, rows=[ROW])
                assert_that((made.held, changed(made.out)), equal_to((after, lines)))

    def test_a_second_agent_takes_the_other_row(self) -> None:
        """Both rows are held, and each takes is told once."""
        made = watchworld.play({"a1": worker("a1", 7), "a2": worker("a2", 8)})
        assert_that(
            (made.held, len(changed(made.out)), printed(made.out, "OVERCAP")),
            equal_to((["a1", "a2"], 2, [])),
        )

    def test_a_third_agent_is_over_the_cap(self) -> None:
        """The extra agent is named every round."""
        made = watchworld.play(
            {n: worker(n, k) for n, k in (("a1", 7), ("a2", 8), ("a3", 9))},
            rounds="3",
        )
        assert_that(
            (made.held, printed(made.out, "OVERCAP"), printed(made.out, "SLOT FREE")),
            equal_to((["a1", "a2"], ["OVERCAP a3 owner/project#9"] * 3, [])),
        )

    def test_the_free_slot_line_names_the_first_startable_item(self) -> None:
        """Silent in the first round, with the brief command from the second."""
        once = watchworld.play({"a1": worker("a1", 9)})
        many = watchworld.play({"a1": worker("a1", 9)}, rounds="3")
        said = "SLOT FREE: 1 of 2 free since 2030-01-01 00:00Z; first startable: "
        assert_that(printed(once.out, "SLOT FREE"), equal_to([]))
        assert_that(len(printed(many.out, "SLOT FREE")), equal_to(2))
        assert_that(printed(many.out, "SLOT FREE")[0], starts_with(said))

    def test_the_marker_line_sets_the_ticket_and_kind(self) -> None:
        """The word SubagentHandback in the prose is not a finish."""
        made = watchworld.play(
            {"a1": [brief("a1", MARKED, RECENT), call("Bash", RECENT)]}
        )
        assert_that((made.held, made.kinds), equal_to((["a1"], ["fix"])))

    def test_a_row_with_no_transcript_is_freed_only_when_older_than_the_process(
        self,
    ) -> None:
        """The process that held an old row is gone; a newer row stays."""
        old = watchworld.play(
            {}, rows=[ROW], clock=watchworld.Clock(when="2029-12-30T00:00:00+00:00")
        )
        new = watchworld.play({}, rows=[ROW])
        assert_that(
            (old.held, changed(old.out), new.held),
            equal_to(([], [FREED.format("no transcript")], ["a1"])),
        )

    def test_a_file_that_is_not_a_transcript_is_skipped(self) -> None:
        """A task output with no agent id holds no slot."""
        here = watchworld.planted({"b1": [], "b2": []})
        for name, text in (("b1", "plain output\n"), ("b2", "{}\n")):
            (here.workspace / "tasks" / f"{name}.output").write_text(text)
        assert_that(watchworld.watch(here).out, equal_to(""))

    def test_a_brief_with_no_marker_or_goal_is_unmarked_once_and_holds_no_slot(
        self,
    ) -> None:
        """No reference in the brief: an UNMARKED line, said once, and no row."""
        made = watchworld.play(
            {"a1": [brief("a1", "do something", RECENT), call("Bash", RECENT)]},
            rounds="3",
        )
        assert_that(
            (made.held, printed(made.out, "UNMARKED")),
            equal_to(
                (
                    [],
                    [
                        "UNMARKED a1: its brief has no PITBOSS-SLOT or Goal line, "
                        "so it holds no slot"
                    ],
                )
            ),
        )

    def test_without_a_directory_it_refuses(self) -> None:
        """The configuration names none."""
        found = watchworld.watch(world.make_world())
        assert_that((found.code, found.err.endswith(NEEDS)), equal_to((2, True)))

    def test_a_damaged_line_is_read_over(self) -> None:
        """The records around a line that is no JSON still tell the state."""
        here = watchworld.planted({"a1": worker("a1", 7)})
        with (here.workspace / "tasks" / "a1.output").open("a") as stream:
            stream.write("{not json\n")
        watchworld.watch(here)
        assert_that(watchworld.held(here), equal_to(["a1"]))

    def test_with_no_start_given_the_process_is_asked(self) -> None:
        """No ``--process-start``: ``ps`` is read, and an empty round is quiet."""
        here = watchworld.planted({})
        words = ("watch", "--rounds", "1", "--interval", "0", "--now", watchworld.NOW)
        made = slots(here, *words)
        assert_that((made.code, agenttranscript.ending([])), equal_to((0, None)))
