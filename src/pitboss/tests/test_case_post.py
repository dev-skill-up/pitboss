"""A19 and A31: ``pitboss case post`` edits the ticket's body, never a comment.

Owner, 2026-11-08T23:06Z and 21:02Z: the Done-when and the cases are in the body,
changed only before a worker started; a started PR gets nothing added
(pitboss#444, keyword: case-post).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, empty, equal_to

from .. import casepost, config
from . import fakes, refused, world
from .says import exits

TICKET = f"{world.PROJECT}/issues/9"
PATCH = f"PATCH {TICKET}"
LISTED = fakes.page("/".join([world.PROJECT, "pulls?state=closed"]))
BODY = (
    "Intro.\n\n## Done when\n\n1. Old, demonstrated by a test.\n\n## History\n\nMore.\n"
)
NEW = "1. New, demonstrated by a test.\n2. Newer, demonstrated by a test.\n"
CASE = "Case 1 (2026-11-12): a thing happened.\n"
EDITABLE = {TICKET: {"body": BODY}, PATCH: {}}
REPO = config.make_repo("owner", "project")


def case_world(pulls: Sequence[object]) -> world.World:
    """A world whose ticket 9 has a body and whose repository has some PRs.

    Args:
        pulls: the PRs of the repository.

    Returns:
        The world.
    """
    return refused.world_of({**EDITABLE, LISTED: list(pulls)})


def post(here: world.World, text: str, *options: str) -> world.Result:
    """Run ``case post`` on ticket 9 of the project.

    Args:
        here: the world.
        text: the file's text.
        *options: more options.

    Returns:
        What it did.
    """
    argv = ("case", "post", "owner/project#9", refused.FILE, *options)
    return refused.run(here, text, *argv)


def started(number: int = 4, says: str = "Fixes #9") -> Sequence[object]:
    """A PR whose body says what it fixes.

    Args:
        number: its number.
        says: its body.

    Returns:
        The PRs the list has.
    """
    return [{"number": number, "body": says}]


class TestDoneWhen(unittest.TestCase):
    """The Done-when is replaced in the body before a worker started."""

    def test_a19_the_done_when_is_edited_in_the_body(self) -> None:
        """The section is the file; the rest of the body is as it was; no comment."""
        here = case_world([])
        done = post(here, NEW, "--done-when")
        assert_that(done.out, equal_to("https://github.com/owner/project/issues/9\n"))
        assert_that(
            refused.bodies(here),
            equal_to([BODY.replace("1. Old, demonstrated by a test.\n", NEW)]),
        )
        assert_that([each for each in here.calls if "comments" in each[-1]], empty())

    def test_a19_the_edit_is_refused_once_a_worker_started(self) -> None:
        """A PR says it fixes the ticket."""
        here = case_world(started())
        done = post(here, NEW, "--done-when")
        refused.assert_refused(done, "PR #4 says it fixes owner/project#9", here)

    def test_a19_a_ticket_with_no_done_when_gets_the_section(self) -> None:
        """The section is added at the end."""
        assert_that(
            casepost.with_done_when("Intro.\n", NEW),
            equal_to("Intro.\n\n## Done when\n\n" + NEW + "\n"),
        )

    def test_a19_a_ticket_that_is_no_reference_is_refused(self) -> None:
        """The file is read first; the reference is refused with its reason."""
        here = case_world([])
        done = refused.run(here, CASE, "case", "post", "nine", refused.FILE)
        refused.assert_refused(done, "nine: not OWNER/NAME#NUMBER", here)


class TestAddition(unittest.TestCase):
    """A started ticket gets nothing added."""

    def test_a31_an_addition_to_a_started_ticket_is_refused(self) -> None:
        """New findings go to an older open ticket."""
        here = case_world(started(says="Fixes owner/project#9\n\nBody."))
        done = post(here, CASE)
        refused.assert_refused(done, "file the new finding on an older open", here)

    def test_a31_a_case_is_added_before_a_worker_started(self) -> None:
        """The nearest input it must still accept: a PR that fixes another ticket."""
        here = case_world(started(says="Fixes #10"))
        exits(post(here, CASE), 0)
        assert_that(refused.bodies(here), equal_to([BODY + "\n" + CASE]))

    def test_a31_a_pr_with_no_body_started_nothing(self) -> None:
        """A PR whose body is null names no ticket."""
        found = casepost.started_by("owner/project#9", [(3, "")], REPO)
        assert_that(found, equal_to(0))
