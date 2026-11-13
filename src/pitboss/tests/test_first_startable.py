"""The ``SLOT FREE`` line when the queue holds back the rest (pitboss#415)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import decisionline, fakes, watchworld, world
from .rankworld import blocked_world
from .test_slot_commands import next_output
from .test_not_the_head import QUEUE, fill
from .ownerbodies import lines_of
from .test_slots_watch import worker
from .transcripts import write

NONE = (
    "NOT ENOUGH WORK: no open pull request and no ticket of the priority labels can"
    " be started now"
)


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

    def test_the_first_decision_is_handed_over(self) -> None:
        """A worker runs on ticket 9: the first decision is the next ticket's."""
        said = free_lines(QUEUE, "")
        first = "first startable: WORKER: owner/project#12: write the code"
        assert_that((len(said), first in said[0]), equal_to((2, True)))

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
    """The decision of PR 3 in ``slots next`` at a CI state.

    Args:
        checks: ``red``, ``green`` or ``pending``.

    Returns:
        The line, empty when PR 3 has no decision.
    """
    here = world.make_world()
    open_pull_3(here, CHECKS[checks])
    return decisionline.of(next_output(here), "owner/project#3")


class TestSkipped(unittest.TestCase):
    """What the first startable item is not."""

    def test_a_pr_whose_ci_is_not_green_is_not_offered_for_review(self) -> None:
        """Red is a fix of the CI, pending is skipped, green is the review."""
        found = {name: start_for(name) for name in CHECKS}
        assert_that(
            {
                name: ("REVIEWER" in line, "fix CI on the head" in line)
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
        assert_that(found["pending"], equal_to(""))

    def test_a_blocked_ticket_offers_its_blocker_with_its_priority_and_age(
        self,
    ) -> None:
        """The blocker takes the blocked ticket's place; the blocked one is in none."""
        listed = next_output(blocked_world())
        lib = decisionline.of(listed, "owner/lib#3")
        assert_that(
            [decisionline.of(listed, "owner/project#9"), lib.startswith("NEXT 3 of")],
            equal_to(["", True]),
        )
