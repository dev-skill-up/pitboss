"""The owner's rules of the order of work, on the one path (keyword: one-path).

Each test names the rule of ``rules.tsv`` it shows: the tickets an open pull
request works on are taken, the order is the pull requests, then the tickets by
label and age across the repositories, then the relock pull requests, a blocker
takes the place of what it blocks, and a waiting item is in no answer.
"""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brieftextwork
from . import fakes, liveagents
from . import world as fixture

PULLS = fakes.page(f"{fixture.PROJECT}/pulls?state=open")
LIBRARY_TICKETS = fakes.page(f"{fixture.LIBRARY}/issues?state=open&labels=urgent")
NEXT_ITEM = re.compile(r"^NEXT \d+ of \d+\. [A-Z]+: (\S+):", re.MULTILINE)
PLAN = "\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"


def items(here: fixture.World) -> Sequence[str]:
    """The items of the ``NEXT`` lines of ``slots next``, in their order.

    Args:
        here: the world.

    Returns:
        Each line's ``owner/name#number``.
    """
    output = liveagents.next_output(here)
    return [found.group(1) for found in NEXT_ITEM.finditer(output)]


def with_body(here: fixture.World, number: int, body: str) -> None:
    """Give an open pull request of the project a body, in its listing and details.

    Args:
        here: the world.
        number: its number.
        body: the body.
    """
    here.bodies[PULLS] = [
        fakes.pull_body(each, body=body) if each == number else fakes.pull_body(each)
        for each in (1, 2, 3)
    ]
    sha = fakes.HEAD if number == 2 else str(number) * 40
    head = {"sha": sha, "ref": f"branch-{number}"}
    here.bodies[f"{fixture.PROJECT}/pulls/{number}"] = fakes.pull_body(
        number, head=head, body=body, mergeable_state=fixture.PULLS[number - 1][3]
    )


def issue(number: int) -> Mapping[str, object]:
    """An open ticket of the library, older than the project's, as GitHub gives it.

    Args:
        number: its number.

    Returns:
        The issue.
    """
    return {
        "number": number,
        "state": "open",
        "title": f"library ticket {number}",
        "created_at": "2026-08-01T00:00:00Z",
        "labels": [{"name": "urgent"}],
    }


def library_world(number: int) -> fixture.World:
    """A world whose library has an open ticket that can be read by its reference.

    Args:
        number: its number.

    Returns:
        The world.
    """
    here = fixture.make_world()
    here.bodies[f"{fixture.LIBRARY}/issues/{number}"] = issue(number)
    return here


class TestOrder(unittest.TestCase):
    """What the walk offers, and in which order."""

    def test_b7_a_ticket_an_open_pull_request_fixes_is_not_offered(self) -> None:
        """Ticket 9 is offered until pull request 2 says it fixes it."""
        here = fixture.make_world()
        before = items(here)
        with_body(here, 2, f"Fixes #9{PLAN}")
        assert_that(
            ("owner/project#9" in before, "owner/project#9" in items(here)),
            equal_to((True, False)),
        )

    def test_b9_pull_requests_come_first_then_tickets_by_age_across_repositories(
        self,
    ) -> None:
        """The pull requests, then an older library ticket before the project's."""
        here = library_world(5)
        here.bodies[LIBRARY_TICKETS] = [issue(5)]
        wanted = ["owner/project#1", "owner/project#3", "owner/lib#5"]
        assert_that(items(here), equal_to([*wanted, "owner/project#9"]))

    def test_c7_a_relock_pull_request_comes_after_the_tickets(self) -> None:
        """Pull request 3 on a relock branch is offered after ticket 9."""
        here = fixture.make_world()
        relock = {"sha": "3" * 40, "ref": "relock/2026-11-13"}
        here.bodies[PULLS] = [
            fakes.pull_body(1),
            fakes.pull_body(2),
            fakes.pull_body(3, head=relock),
        ]
        assert_that(items(here)[-2:], equal_to(["owner/project#9", "owner/project#3"]))

    def test_i17_a_mention_of_a_ticket_does_not_take_it(self) -> None:
        """Pull request 2 fixes another ticket and only mentions 9: 9 is offered."""
        here = fixture.make_world()
        with_body(here, 2, f"Fixes #2\n\nthe ruling mentions #9{PLAN}")
        assert_that("owner/project#9" in items(here), equal_to(True))


class TestBlockers(unittest.TestCase):
    """A blocker is examined in the place of what it blocks."""

    def test_b10_i26_a_blocker_takes_the_place_of_the_blocked_pull_request(
        self,
    ) -> None:
        """Pull request 3 is in no answer; the ticket it names is in its place."""
        here = library_world(7)
        with_body(here, 3, f"Fixes #3\n\nBlocked by owner/lib#7{PLAN}")
        found = items(here)
        assert_that(found, equal_to(["owner/project#1", "owner/lib#7", found[-1]]))
        assert_that(found[-1], equal_to("owner/project#9"))


class TestBriefs(unittest.TestCase):
    """What a worker is told."""

    def test_b21_a_worker_brief_says_never_to_change_the_draft_state(self) -> None:
        """The brief of the ticket's worker carries the draft-state sentence."""
        output = liveagents.next_output(fixture.make_world())
        assert_that(output, contains_string(brieftextwork.DRAFT_STATE))
