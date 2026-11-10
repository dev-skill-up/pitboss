"""The ``SLOT FREE`` line when the queue holds back the rest (pitboss#415)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import watchworld, world
from . import fakes
from .rankworld import blocked_world
from .test_slot_commands import next_output
from .test_not_the_head import QUEUE, fill
from .test_owner_repositories import lines_of
from .test_slots_watch import worker
from .transcripts import write

SERIAL = 'serial = ["owner/project"]\n'
SKIPPED = "offered because a ticket of its repository is in flight"
NONE = "no open ticket or PR is queued: file the next ticket"


def free_lines(tickets: Mapping[int, tuple[str, str]], extra: str) -> Sequence[str]:
    """What the watcher says of a free slot, with a worker on a ticket running.

    Args:
        tickets: each ticket's number, label and state.
        extra: more keys of ``[slots]``.

    Returns:
        The ``SLOT FREE`` lines of three rounds.
    """
    here, directory = watchworld.watched(extra)
    fill(here, tickets)
    write(directory, "a1", worker("a1", 9))
    return lines_of(watchworld.watch(here, "3").out, "SLOT FREE")


class TestFirstStartable(unittest.TestCase):
    """What the line offers when nothing may start."""

    def test_a_serial_repository_hands_over_its_head_with_the_reason(self) -> None:
        """Every ticket of the repository is held while one runs."""
        said = free_lines(QUEUE, SERIAL)
        assert_that(
            (len(said), SKIPPED in said[0], "owner/project#12 (" in said[0]),
            equal_to((2, True, True)),
        )

    def test_an_empty_queue_says_to_file_a_ticket(self) -> None:
        """No ticket and no PR at all."""
        said = free_lines({}, "")
        assert_that(said[0].endswith(NONE), equal_to(True))


RUN = {
    "id": 8,
    "name": "test",
    "status": "completed",
    "started_at": "2026-10-01T09:50:00Z",
}
PENDING = dict(RUN, status="in_progress")
CHECKS = {
    "red": [dict(RUN, conclusion="failure", completed_at="2026-10-01T10:00:00Z")],
    "green": [dict(RUN, conclusion="success", completed_at="2026-10-01T10:00:00Z")],
    "pending": [PENDING],
}


def open_pull_3(here: world.World, runs: Sequence[object]) -> None:
    """Make PR 3 the only open PR, its head with these check runs.

    Args:
        here: the world.
        runs: the check runs of its head.
    """
    sha = "3" * 40
    path = world.PROJECT
    here.bodies.update(
        {
            f"{path}/pulls/3": fakes.pull_body(3, head={"sha": sha, "ref": "b-3"}),
            fakes.page(f"{path}/commits/{sha}/check-runs"): {"check_runs": [*runs]},
            fakes.page(f"{path}/commits/main/check-runs"): {"check_runs": []},
            fakes.page(f"{path}/pulls?state=open"): [{"number": 3}],
        }
    )


def start_for(checks: str) -> str:
    """The START line of ``slots next`` with PR 3 at a CI state.

    Args:
        checks: ``red``, ``green`` or ``pending``.

    Returns:
        The line.
    """
    here = world.make_world()
    open_pull_3(here, CHECKS[checks])
    return lines_of(next_output(here), "START")[0]


class TestSkipped(unittest.TestCase):
    """What the first startable item is not."""

    def test_a_pr_whose_ci_is_not_green_is_not_offered_for_review(self) -> None:
        """Red is a fix of the CI, pending is skipped, green is the review."""
        found = {name: start_for(name) for name in CHECKS}
        assert_that(
            {
                name: ("review it" in line, "fix the CI" in line)
                for name, line in found.items()
            },
            equal_to(
                {
                    "red": (False, True),
                    "green": (True, False),
                    "pending": (False, False),
                }
            ),
        )
        assert_that("owner/project#9 (start a PR" in found["pending"], equal_to(True))

    def test_a_blocked_ticket_offers_its_blocker_with_its_priority_and_age(
        self,
    ) -> None:
        """The blocker takes the blocked ticket's label and date."""
        listed = "\n".join(lines_of(next_output(blocked_world()), "NEXT"))
        assert_that(
            [
                "owner/project#9 (" in listed,
                "owner/lib#3 (start a PR urgent, opened 2026-09-01" in listed,
            ],
            equal_to([False, True]),
        )

    def test_a_serial_repository_is_held_while_a_pr_of_it_is_open(self) -> None:
        """A pending PR holds the repository's tickets; without the key none is."""
        out = {}
        for extra in (SERIAL, ""):
            here, _ = watchworld.watched(extra)
            open_pull_3(here, [PENDING])
            out[extra] = lines_of(next_output(here), "START")
        assert_that(
            (
                "owner/project#9" in "".join(out[SERIAL]),
                "owner/project#9" in "".join(out[""]),
            ),
            equal_to((False, True)),
        )
