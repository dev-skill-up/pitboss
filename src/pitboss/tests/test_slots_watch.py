"""``slots watch`` keeps the ledger from the agents' transcripts (pitboss#415)."""

import unittest
from typing import Sequence

from hamcrest import (
    assert_that,
    equal_to,
    starts_with,
)

from . import watchworld, world
from .test_owner_repositories import lines_of as printed
from .transcripts import brief, call, ended, interrupted, turn_end
from .watchworld import FREED, GOAL, MARKED, OLD, QUIET, RECENT, TAKES

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
        old = watchworld.play({}, rows=[ROW], when="2029-12-30T00:00:00+00:00")
        new = watchworld.play({}, rows=[ROW])
        assert_that(
            (old.held, changed(old.out), new.held),
            equal_to(([], [FREED.format("no transcript")], ["a1"])),
        )

    def test_a_file_that_is_not_a_transcript_is_skipped(self) -> None:
        """A task output with no agent id holds no slot."""
        here, directory = watchworld.watched()
        directory.mkdir()
        (directory / "b1.output").write_text("plain output\n")
        (directory / "b2.output").write_text("{}\n")
        assert_that(watchworld.watch(here).out, equal_to(""))

    def test_a_brief_with_no_ticket_takes_a_row_naming_none(self) -> None:
        """No reference in the brief."""
        made = watchworld.play({"a1": [brief("a1", "do something", RECENT)]})
        assert_that(changed(made.out), equal_to([TAKES.format("no ticket")]))

    def test_without_a_directory_it_refuses(self) -> None:
        """The configuration names none."""
        found = watchworld.watch(world.make_world())
        assert_that((found.code, found.err.endswith(NEEDS)), equal_to((2, True)))
