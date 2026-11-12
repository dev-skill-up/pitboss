"""I10, I14 and I30: an approved Plan stays approved, and a check posts itself.

Cases 10, 14 and 30 of pitboss#444 (keyword: plan-prior). An approved Plan that a
later head or a merge of main left with an older run in its CI pointers is not
refused again (10, 30); ``plan-check --post`` writes the comment with the heading
``Plan check`` itself (14).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import pullfile
from . import checkcomment, fakes, refused, world
from .linting import write_text
from .repositories import run_git
from .test_plan_check_remote import (
    clone_head,
    full_plan,
    run_check,
    ticket_world,
    with_pointer,
)

COMMENTS = "repos/owner/project/issues/7/comments"
POSTED = f"POST {COMMENTS}"
URL = "https://github.example/owner/project/pull/7#c9"
EARLIER_URL = "https://github.example/owner/project/pull/7#c2"
PULL = ("--pull", "owner/project#7")


def approved_world() -> tuple[world.World, str]:
    """A world whose PR 7 has an ok Plan check, and a head made after it.

    Returns:
        The world, and the commit the Plan check was made at (the run's head).
    """
    here = ticket_world()
    earlier = clone_head(here)
    run_git(here.clone, "commit", "--allow-empty", "-m", "a later head")
    plan = with_pointer(full_plan())
    comment = {
        "body": checkcomment.clean_text(plan),
        "author_association": "MEMBER",
        "created_at": "2026-11-11T00:00:00Z",
        "html_url": EARLIER_URL,
    }
    here.bodies[fakes.page(COMMENTS)] = [comment]
    here.bodies["repos/owner/project/actions/runs/5"] = {"head_sha": earlier}
    return here, earlier


def lines_of(here: world.World, *options: str) -> Sequence[str]:
    """Run the check of the Plan with a pointer to run 5.

    Args:
        here: the world.
        *options: more options.

    Returns:
        The exit status and the lines.
    """
    return run_check(here, "owner/project#9", with_pointer(full_plan()), *options)


def ci_run_refused(here: world.World, *options: str) -> None:
    """Assert the check names a ``ci-run:`` finding.

    Args:
        here: the world.
        *options: more options.
    """
    found = "\n".join(lines_of(here, *options))
    assert_that(found, contains_string("ci-run:"))


class TestPrior(unittest.TestCase):
    """The run of an earlier head and the ticket are not judged again."""

    def test_i10_i30_the_run_of_the_head_it_was_approved_at_passes(self) -> None:
        """A merge of main moved the head; the Plan is as the ok check had it."""
        here, _ = approved_world()
        text = "\n".join(lines_of(here, *PULL))
        assert_that(text, contains_string(EARLIER_URL))
        assert_that("ci-run:" not in text, "no ci-run finding")

    def test_i10_i30_without_the_pull_the_old_run_is_refused(self) -> None:
        """No --pull, no record: the run of another commit is a finding."""
        here, _ = approved_world()
        ci_run_refused(here)

    def test_i10_i30_an_edited_plan_has_no_prior_check(self) -> None:
        """The comment records another digest: the run is refused as before."""
        here, _ = approved_world()
        comment = {
            "body": checkcomment.clean_text("## Plan\nanother plan\n"),
            "author_association": "MEMBER",
            "created_at": "2026-11-11T00:00:00Z",
            "html_url": EARLIER_URL,
        }
        here.bodies[fakes.page(COMMENTS)] = [comment]
        ci_run_refused(here, *PULL)

    def test_i10_i30_a_run_of_a_commit_the_head_lacks_is_refused(self) -> None:
        """A run of a commit that is not behind the head is no earlier head."""
        here, _ = approved_world()
        here.bodies["repos/owner/project/actions/runs/5"] = {"head_sha": "c" * 40}
        ci_run_refused(here, *PULL)

    def test_i10_a_pull_that_is_no_reference_is_refused(self) -> None:
        """The option is OWNER/NAME#NUMBER."""
        here, _ = approved_world()
        path = write_text("body.txt", "## Plan\nx\n")
        done = world.invoke(here, "plan-check", path, "--pull", "seven")
        said = "seven: not OWNER/NAME#NUMBER" in done.err
        assert_that((done.code, said), equal_to((2, True)))


class TestPost(unittest.TestCase):
    """I14: the output is posted by the command."""

    def test_i14_the_comment_is_the_output_with_its_heading(self) -> None:
        """First line `Plan check`, last `Plan check: ok`."""
        here, _ = approved_world()
        here.bodies[POSTED] = {"id": 9, "html_url": URL}
        shown = lines_of(here, "--post", "owner/project#7")
        posted = refused.bodies(here)
        assert_that(posted[0].splitlines()[0], equal_to("Plan check"))
        assert_that(posted[0].splitlines()[-1], equal_to(shown[-1]))
        assert_that(posted[0], equal_to("\n".join(shown[1:]) + "\n"))
        assert_that(
            pullfile.split("plan-check", "owner/project#7"),
            equal_to(("owner/project", 7)),
        )
