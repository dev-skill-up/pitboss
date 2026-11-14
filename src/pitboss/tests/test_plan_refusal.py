"""A PR whose newest ``Plan check`` refuses the Plan waits for what it names (#388).

The cause: pitboss#372 was refused by plan-check until pitboss#373 landed, and the
sweep still offered its review round. A waiting PR has no decision and nothing is
said of it; the open blocker it names is offered in its place (keyword: one-path).
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import planrefusal
from . import fakes, rankworld, world
from .pinsworld import offered as third_of
from .rankworld import starts, sweep

COMMENTS = "repos/owner/project/issues/3/comments"
SEVEN = "owner/project#7"
THIRD = "owner/project#3"
REFUSED = "WORKER: owner/project#3: the Plan check is refused"
DIGEST = "Plan digest: afbee19f3c5134c8"


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
    comments: Sequence[Mapping[str, str]], seventh: str = "open"
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
    here.bodies[fakes.page(COMMENTS)] = list(comments)
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
    """The answer of ``slots next``."""

    def test_the_refusal_blocks_the_pull_request(self) -> None:
        """No decision for PR 3; the blocker is offered in its place."""
        here = refused_world([refusal()])
        offered = ["owner/project#1", SEVEN, "owner/project#10"]
        assert_that(starts(here), equal_to(offered))
        assert_that(third_of(here), equal_to(""))

    def test_every_spelling_of_a_name_blocks(self) -> None:
        """``#7``, ``owner/project#7`` and the issue's URL name the same ticket."""
        url = "https://github.com/owner/project/issues/7"
        for names in ("#7", SEVEN, url):
            with self.subTest(names):
                here = refused_world([refusal(names)])
                found = (third_of(here), SEVEN in starts(here))
                assert_that(found, equal_to(("", True)))

    def test_a_ticket_that_is_closed_blocks_no_more(self) -> None:
        """Ticket 7 is closed: PR 3 has its decision again."""
        here = refused_world([refusal()], "closed")
        assert_that(third_of(here), contains_string(REFUSED))

    def test_a_newer_ok_unblocks(self) -> None:
        """The newest ``Plan check`` says ok: PR 3 has a decision again."""
        assert_that(third_of(refused_world([refusal(), OK])), contains_string(THIRD))

    def test_the_pull_request_and_its_ticket_are_not_blockers(self) -> None:
        """A refusal that names PR 3 and ticket 9 blocks nothing."""
        here = refused_world([refusal("#3 and #9")])
        assert_that(third_of(here), contains_string(REFUSED))

    def test_an_untrusted_comment_is_not_read(self) -> None:
        """A refusal from an author who is not a member does not block."""
        here = refused_world([check(refusal()["body"], "NONE")])
        assert_that(SEVEN in starts(here), equal_to(False))
        assert_that(third_of(here), contains_string(THIRD))

    def test_the_blocker_is_joined_to_those_of_the_ticket(self) -> None:
        """The ticket depends on owner/lib#3 and the check names ticket 7."""
        here = refused_world([refusal()])
        rankworld.serve(here, "owner/project", 9, rankworld.ticket(rankworld.DEPENDENT))
        here.bodies[rankworld.BLOCKER] = dict(rankworld.LIB_THREE)
        offered = starts(here)
        named = [each in offered for each in ("owner/lib#3", SEVEN)]
        assert_that(named, equal_to([True, True]))
        assert_that(third_of(here), equal_to(""))


class TestSweep(unittest.TestCase):
    """The sweep prints the same answer."""

    def test_the_pull_request_has_no_decision(self) -> None:
        """No line decides PR 3; the blocker is offered."""
        out = sweep(refused_world([refusal()])).out
        assert_that(f": {THIRD}: " in out, equal_to(False))
        assert_that(out, contains_string(f": {SEVEN}: write the code"))

    def test_a_closed_ticket_or_an_ok_gives_the_decision_back(self) -> None:
        """With no blocker the PR is decided again (the refusal, #471)."""
        for comments, seventh in (([refusal()], "closed"), ([refusal(), OK], "open")):
            with self.subTest(seventh):
                out = sweep(refused_world(comments, seventh)).out
                assert_that(out, contains_string(REFUSED))
