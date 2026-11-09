"""A PR whose newest ``Plan check`` refuses the Plan waits for what it names (#388).

The cause: pitboss#372 was refused by plan-check until pitboss#373 landed, and the
sweep still offered its review round.
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import planrefusal
from . import rankworld, world
from .rankworld import lines_are, next_output, printed, starts, sweep

COMMENTS = "repos/owner/project/issues/3/comments"
SEVEN = "owner/project#7"
BLOCKED = f"BLOCKED owner/project#3 by {SEVEN}"
STEP = "PR STATE owner/project#3"
TASK = "TASK LIST next 3. owner/project#3"
DIGEST = "Plan digest: " + "0" * 64


def check(text: str, association: str = "MEMBER") -> Mapping[str, str]:
    """A comment of PR 3.

    Args:
        text: its text.
        association: its author's association.

    Returns:
        The JSON of the comment.
    """
    return rankworld.comment(text, association)


def refusal(names: str = "#7") -> Mapping[str, str]:
    """A refusing ``Plan check`` comment that names something.

    Args:
        names: how it names the ticket or PR.

    Returns:
        The JSON of the comment.
    """
    lines = ["Plan check", f"row 3: needs {names} to land", DIGEST]
    return check("\n".join([*lines, "Plan check: refused, rows that did not run: 3"]))


OK = check(f"Plan check\n{DIGEST}\nPlan check: ok")


def refused_world(
    comments: list[Mapping[str, str]], seventh: str = "open"
) -> world.World:
    """PR 3 fixes ticket 9, which names no blocker, and ticket 7 is as given.

    Args:
        comments: the comments of PR 3, oldest first.
        seventh: the state of ticket 7.

    Returns:
        The world.
    """
    here = rankworld.blocked_world("A ticket that depends on nothing")
    rankworld.serve(here, "owner/project", 9, rankworld.ticket(""))
    rankworld.fixing(here, 3, "Fixes #9")
    rankworld.serve(here, "owner/project", 7, rankworld.ticket("", seventh, 7))
    here.bodies[world.fakes.page(COMMENTS)] = list(comments)
    return here


class TestRefusal(unittest.TestCase):
    """What the comments of a PR say."""

    def test_the_newest_check_decides(self) -> None:
        """A refusal that a later ok replaces is no refusal, and the reverse."""
        refused, ok = refusal()["body"], OK["body"]
        cases = {
            "none": ([], ""),
            "no check": (["Looks fine"], ""),
            "ok": ([ok], ""),
            "refused": ([refused], refused),
            "ok after": ([refused, ok], ""),
            "refused after": ([ok, refused, "Thanks"], refused),
        }
        for label, (texts, expected) in cases.items():
            with self.subTest(label):
                assert_that(planrefusal.refusing(texts), equal_to(expected))


class TestSlotsNext(unittest.TestCase):
    """The offer of ``slots next``."""

    def test_the_refusal_blocks_the_pull_request(self) -> None:
        """No step for PR 3; the blocker is listed in its place."""
        here = refused_world([refusal()])
        printed(here, "BLOCKED", [BLOCKED])
        assert_that(
            starts(here), equal_to(["owner/project#1", SEVEN, "owner/project#10"])
        )
        rankworld.absent(next_output(here), STEP)

    def test_every_spelling_of_a_name_blocks(self) -> None:
        """``#7``, ``owner/project#7`` and the issue's URL name the same ticket."""
        url = "https://github.com/owner/project/issues/7"
        for names in ("#7", SEVEN, url):
            with self.subTest(names):
                here = refused_world([refusal(names)])
                printed(here, "BLOCKED", [BLOCKED])

    def test_a_ticket_that_is_closed_blocks_no_more(self) -> None:
        """Ticket 7 is closed: the step of PR 3 is back."""
        here = refused_world([refusal()], "closed")
        printed(here, "BLOCKED", [])
        assert_that(next_output(here), contains_string(STEP))

    def test_a_newer_ok_unblocks(self) -> None:
        """The newest ``Plan check`` says ok: the step is back."""
        here = refused_world([refusal(), OK])
        printed(here, "BLOCKED", [])
        assert_that(next_output(here), contains_string(STEP))

    def test_the_pull_request_and_its_ticket_are_not_blockers(self) -> None:
        """A refusal that names PR 3 and ticket 9 blocks nothing."""
        here = refused_world([refusal("#3 and #9")])
        printed(here, "BLOCKED", [])
        assert_that(next_output(here), contains_string(STEP))

    def test_an_untrusted_comment_is_not_read(self) -> None:
        """A refusal from a author who is not a member does not block."""
        refused = check(refusal()["body"], "NONE")
        here = refused_world([refused])
        printed(here, "BLOCKED", [])

    def test_the_blocker_is_joined_to_those_of_the_ticket(self) -> None:
        """The ticket depends on owner/lib#3 and the check names ticket 7."""
        here = refused_world([refusal()])
        rankworld.serve(here, "owner/project", 9, rankworld.ticket(rankworld.DEPENDENT))
        here.bodies[rankworld.BLOCKER] = dict(rankworld.LIB_THREE)
        both = f"BLOCKED owner/project#3 by owner/lib#3, {SEVEN}"
        printed(here, "BLOCKED", [both])


class TestSweep(unittest.TestCase):
    """The sweep prints the same."""

    def test_the_line_stands_in_place_of_the_step(self) -> None:
        """BLOCKED once, and no task for PR 3."""
        out = sweep(refused_world([refusal()])).out
        lines_are(out, "BLOCKED", [BLOCKED])
        rankworld.absent(out, TASK)

    def test_a_closed_ticket_or_an_ok_gives_the_step_back(self) -> None:
        """Without a standing refusal the sweep lists PR 3 as before."""
        for comments, seventh in (([refusal()], "closed"), ([refusal(), OK], "open")):
            with self.subTest(seventh):
                out = sweep(refused_world(comments, seventh)).out
                lines_are(out, "BLOCKED", [])
                assert_that(out, contains_string(TASK))
