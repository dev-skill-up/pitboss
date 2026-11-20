"""The status and the task list are printed from state, never typed (pitboss#471)."""

import dataclasses
import datetime
import unittest

from .. import checkin, ledger, slotbook, steps, tasklistlines
from .. import world as world_module
from . import fakes, suggestions, world
from .cleanworld import same
from .test_decide import answer_of, ticket

NOW = datetime.datetime(2026, 11, 11, 10, 21, 13, tzinfo=datetime.timezone.utc)
LATER = NOW + datetime.timedelta(minutes=30)
BOOK = slotbook.ledger_of(())
STALE = "two Opus rulings (pitboss#459 and #460) await a permission decision"
SLOT = dataclasses.replace(
    slotbook.empty_slot("s1", "m"), agent="a1", task="o/r#9", ticket="o/r#9"
)
CLOSED = "repos/o/r/pulls?state=closed&sort=updated&direction=desc&per_page=30"


class TestCheckinLine(unittest.TestCase):
    """The real time of the firing, the next due time and the expiry."""

    def test_the_line_is_computed_from_the_firing(self) -> None:
        """10:21Z, next 10:51Z, the job expires a week less one interval later."""
        said = checkin.status_line(checkin.record(BOOK, NOW), NOW)
        same(
            said,
            "check-in 10:21Z; next due 10:51Z; job expires 2026-11-18T09:51Z",
        )

    def test_the_first_check_in_stays_until_the_job_is_rearmed(self) -> None:
        """Recorded again it is kept; renewed it is kept; re-armed it moves."""
        old = checkin.record(BOOK, NOW)
        firsts = [
            checkin.record(old, LATER).checkin_first,
            checkin.renew(old, LATER).checkin_first,
            checkin.rearm(old, LATER).checkin_first,
        ]
        same(firsts, [NOW.isoformat(), NOW.isoformat(), LATER.isoformat()])

    def test_the_ledger_keeps_the_first_check_in(self) -> None:
        """Written, and read back."""
        path = fakes.directory() / "ledger.json"
        ledger.write(path, checkin.record(BOOK, NOW))
        kept = ledger.read(path, ())
        same(kept.checkin_first, NOW.isoformat())
        same(NOW.isoformat() in path.read_text(), True)


class TestPrompt(unittest.TestCase):
    """The cron prompt holds commands, and a stale line is no part of the status."""

    def test_the_prompt_has_the_commands_that_print_the_status(self) -> None:
        """Checkin, sweep, tasklist, and a rule that nothing is added."""
        wanted = ["slots checkin", "pitboss sweep", "slots tasklist", "no line of your"]
        same([each in checkin.PROMPT for each in wanted], [True] * len(wanted))

    def test_a_stale_line_in_a_prompt_is_not_in_the_printed_status(self) -> None:
        """The output is made from the ledger and GitHub alone."""
        prompt = f"{checkin.PROMPT}\nNote: {STALE}\n"
        given = answer_of(world_module.Exhausted(examined=[]))
        shown = tasklistlines.lines(
            slotbook.ledger_of((SLOT,)),
            given,
            [],
            NOW,
        )
        same((STALE in prompt, any(STALE in each for each in shown)), (True, False))


class TestTaskList(unittest.TestCase):
    """One line for each ticket or PR, in the checklist format."""

    def test_a_line_for_each_running_merged_and_waiting(self) -> None:
        """The header holds the times; the marks lead the lines; none is grouped."""
        given = answer_of(world_module.Exhausted(examined=[ticket(9), ticket(10)]))
        book = dataclasses.replace(slotbook.ledger_of((SLOT,)), checkin=NOW.isoformat())
        shown = tasklistlines.lines(book, given, ["✓ o/r#8: d (merged)"], NOW)
        same(
            shown[1:],
            [
                "",
                "✱ o/r#9: worker a1 (slot s1)",
                "✓ o/r#8: d (merged)",
                f"○ WORKER: o/r#10: {steps.FIRST_STEP} (ticket 10)",
            ],
        )
        same(shown[0].startswith("Task list: check-in 10:21Z; next due 10:51Z"), True)

    def test_merged_pull_requests_of_the_last_day_are_checked_off(self) -> None:
        """Merged recently; merged long ago and closed unmerged are left out."""
        listed: list[object] = [
            {"number": 1, "title": "new", "merged_at": "2026-11-11T08:00:00Z"},
            {"number": 2, "title": "old", "merged_at": "2026-11-01T08:00:00Z"},
            {"number": 3, "title": "closed", "merged_at": None},
        ]
        bodies: dict[str, object] = {CLOSED: listed}
        found = tasklistlines.merged_recently(fakes.github(bodies), "o/r", NOW)
        same(found, ["✓ o/r#1: new (merged)"])

    def test_a_list_that_cannot_be_read_is_said(self) -> None:
        """No silence: one line says it."""
        found = tasklistlines.merged_recently(fakes.github({}), "o/r", NOW)
        same(found[0].startswith("merged PRs unreadable"), True)
        same("✓" in "".join(found), False)


class TestCommand(unittest.TestCase):
    """``slots tasklist`` prints the list from the world's state."""

    def test_the_command_prints_the_header_and_a_line_for_each_ticket(self) -> None:
        """A header, a blank line, then marked lines; the exit status is 0."""
        found = suggestions.run_command(world.make_world(), "slots", "tasklist")
        shown = found.out.splitlines()
        same(found.code, 0)
        same((shown[0].startswith("Task list: "), shown[1]), (True, ""))
        marks = "✱✓○"
        same(all(each[:1] in marks or "unreadable" in each for each in shown[2:]), True)
