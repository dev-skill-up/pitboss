"""A19 and A31: ``pitboss case post`` edits the ticket's body, never a comment.

Owner, 2026-11-08T23:06Z and 21:02Z: the Done-when and the cases are in the body,
changed only before a worker started; a started PR gets nothing added
(pitboss#444, keyword: case-post).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import casepost, config
from . import fakes, world

TICKET = f"{world.PROJECT}/issues/9"
PATCH = f"PATCH {TICKET}"
LISTED = fakes.page(f"{world.PROJECT}/pulls?state=all")
BODY = (
    "Intro.\n\n## Done when\n\n1. Old, demonstrated by a test.\n\n## History\n\nMore.\n"
)
NEW = "1. New, demonstrated by a test.\n2. Newer, demonstrated by a test.\n"
CASE = "Case 1 (2026-11-12): a thing happened.\n"
REPO = config.make_repo("owner", "project")


def post(
    text: str, pulls: Sequence[object], *options: str
) -> tuple[world.Result, Sequence[str], Sequence[Sequence[str]]]:
    """Run ``case post`` on ticket 9 of the project.

    Args:
        text: the file's text.
        pulls: the PRs of the repository.
        *options: more options.

    Returns:
        What it did, the bodies it sent to GitHub and every call it made.
    """
    here = world.make_world()
    here.bodies[TICKET] = {"body": BODY}
    here.bodies[LISTED] = list(pulls)
    here.bodies[PATCH] = {}
    path = here.workspace / "case.md"
    path.write_text(text, encoding="utf-8")
    done = world.invoke(here, "case", "post", "owner/project#9", str(path), *options)
    sent = [each[each.index("-f") + 1] for each in here.calls if "-f" in each]
    return done, [each.removeprefix("body=") for each in sent], here.calls


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
        """The section is the file; the rest of the body is as it was."""
        done, sent, _ = post(NEW, [], "--done-when")
        assert_that(done.code, equal_to(0))
        assert_that(
            sent, equal_to([BODY.replace("1. Old, demonstrated by a test.\n", NEW)])
        )

    def test_a19_a_comment_is_never_posted(self) -> None:
        """Only the ticket is changed."""
        done, _, calls = post(NEW, [], "--done-when")
        assert_that(done.out, equal_to("https://github.com/owner/project/issues/9\n"))
        assert_that([each for each in calls if "comments" in each[-1]], empty())

    def test_a19_the_edit_is_refused_once_a_worker_started(self) -> None:
        """A PR says it fixes the ticket."""
        done, sent, _ = post(NEW, started(), "--done-when")
        assert_that(done.err, contains_string("PR #4 says it fixes owner/project#9"))
        assert_that((done.code, sent), equal_to((2, [])))

    def test_a19_a_ticket_with_no_done_when_gets_the_section(self) -> None:
        """The section is added at the end."""
        assert_that(
            casepost.with_done_when("Intro.\n", NEW),
            equal_to("Intro.\n\n## Done when\n\n" + NEW + "\n"),
        )

    def test_a19_a_pull_that_is_no_reference_is_refused(self) -> None:
        """The ticket argument is ``OWNER/NAME#NUMBER``."""
        here = world.make_world()
        done = world.invoke(here, "case", "post", "nine", "/nonexistent/x.md")
        assert_that(str(done.code), contains_string("/nonexistent/x.md"))

    def test_a19_a_ticket_that_is_no_reference_is_refused(self) -> None:
        """The file is read first; the reference is refused with its reason."""
        here = world.make_world()
        path = here.workspace / "case.md"
        path.write_text(CASE, encoding="utf-8")
        done = world.invoke(here, "case", "post", "nine", str(path))
        assert_that(done.err, contains_string("nine: not OWNER/NAME#NUMBER"))


class TestAddition(unittest.TestCase):
    """A started ticket gets nothing added."""

    def test_a31_an_addition_to_a_started_ticket_is_refused(self) -> None:
        """New findings go to an older open ticket."""
        done, sent, _ = post(CASE, started(says="Fixes owner/project#9\n\nBody."))
        assert_that(
            done.err, contains_string("file the new finding on an older open ticket")
        )
        assert_that((done.code, sent), equal_to((2, [])))

    def test_a31_a_case_is_added_before_a_worker_started(self) -> None:
        """The nearest input it must still accept: a PR that fixes another ticket."""
        done, sent, _ = post(CASE, started(says="Fixes #10"))
        assert_that(done.code, equal_to(0))
        assert_that(sent, equal_to([BODY + "\n" + CASE]))

    def test_a31_a_pr_with_no_body_started_nothing(self) -> None:
        """A PR whose body is null names no ticket."""
        assert_that(
            casepost.started_by("owner/project#9", [(3, "")], REPO), equal_to(0)
        )
