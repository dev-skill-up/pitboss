"""A draft whose Plan is approved is a NEXT line, not only a PR STATE line (#273).

The cause: ``mark the PR ready`` was printed only as a ``PR STATE`` line near the
end of the sweep, no numbered suggestion carried it, and bats-lang/quire#1057 sat
a draft for an hour while its execution review could not start.
"""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import readyline
from . import world
from .test_flow_sweep import APPROVED, graded, world_with
from .test_slot_commands import next_output

JOBS = world.project_page("actions/runs/11/jobs")


def held_draft() -> world.World:
    """A world whose draft PR 3 has an approved Plan, and a job waits.

    Returns:
        The world.
    """
    return world_with([graded(APPROVED, None, 1)], draft=True)


def quiet_draft() -> world.World:
    """The same draft with no job waiting and an old clear look in the record.

    Returns:
        The world.
    """
    here = held_draft()
    here.bodies[JOBS] = {"jobs": []}
    record = here.clone / ".git" / "pitboss-pressure.log"
    record.write_text("2029-12-31T23:00:00+00:00 none\n")
    return here


def next_lines(here: world.World) -> Sequence[str]:
    """The NEXT lines of ``slots next`` after the running agents' line.

    Args:
        here: the world.

    Returns:
        The lines, in order.
    """
    return re.findall(r"(?m)^NEXT .*$", next_output(here))[1:]


class TestMarkReadyFollowsTheRunningLine(unittest.TestCase):
    """The approved-Plan draft with no hold."""

    def test_the_draft_is_next_2_after_the_running_line(self) -> None:
        """The exact action, above every start and review line."""
        found = next_lines(quiet_draft())
        assert_that(len(found) > 1, equal_to(True))
        assert_that(found[0], starts_with("NEXT 2. owner/project#3 (mark the PR ready"))
        assert_that(found[0], contains_string("update_pull_request draft=false"))
        assert_that(found[1], starts_with("NEXT 3. "))

    def test_no_other_next_line_marks_ready(self) -> None:
        """Only the draft's line does."""
        found = "\n".join(next_lines(quiet_draft()))
        assert_that(found.count("mark the PR ready"), equal_to(1))


class TestAHoldIsANextLineToo(unittest.TestCase):
    """The same draft while the runners show a hold."""

    def test_the_next_line_names_the_hold_and_its_end(self) -> None:
        """No action is offered; the hold and its end are."""
        found = next_lines(held_draft())
        wanted = (
            "NEXT 2. owner/project#3 (" + readyline.HOLD_WORDS + ": mark ready at "
            "2030-01-01T00:15:00+00:00 at the earliest)"
        )
        assert_that(found[0], equal_to(wanted))
        assert_that("mark the PR ready" in "\n".join(found), equal_to(False))

    def test_a_look_that_cannot_be_read_says_the_end_is_unknown(self) -> None:
        """A queue run whose jobs cannot be read holds with no end to give."""
        here = quiet_draft()
        del here.bodies[JOBS]
        assert_that(next_lines(here)[0], contains_string("mark ready at unknown"))

    def test_an_empty_record_with_the_jobs_unreadable_prints_the_unknown_end(
        self,
    ) -> None:
        """No record file and no readable jobs: the list is still printed."""
        here = quiet_draft()
        del here.bodies[JOBS]
        (here.clone / ".git" / "pitboss-pressure.log").unlink()
        assert_that(next_lines(here)[0], contains_string("mark ready at unknown"))

    def test_an_unreadable_record_prints_the_unknown_end(self) -> None:
        """A record that cannot be read does not stop the list."""
        here = quiet_draft()
        del here.bodies[JOBS]
        log = here.clone / ".git" / "pitboss-pressure.log"
        log.unlink()
        log.mkdir()
        assert_that(next_lines(here)[0], contains_string("mark ready at unknown"))


class TestNoDraftNoLine(unittest.TestCase):
    """A world without such a draft is as it was."""

    def test_the_list_starts_at_one_with_its_items(self) -> None:
        """No ready line, so the first NEXT line is a review or a start."""
        found = next_lines(world.make_world())
        assert_that(found[0], starts_with("NEXT 2. "))
        assert_that("mark the PR ready" in found[0], equal_to(False))
