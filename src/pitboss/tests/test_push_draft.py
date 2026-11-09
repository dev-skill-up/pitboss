"""A push to the branch of a draft PR is free; a changed draft state is told (#355)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import draftmoves, pushdraft, shapes
from . import fakes, world
from .test_commands import sweep
from .test_exempt import OTHER_URL, push, remote_to
from .test_quiet import lines, pushes, waiting_world

PULLS = "repos/other/repo/pulls?head=other:{branch}&state=open"
HELD = "RUNNER PRESSURE"
FREE = "the open PR of branch-1 is a draft: a push to a draft is never held"
READY = {"event": "ready_for_review", "created_at": "2029-12-31T20:00:00Z"}
CONVERTED = {"event": "convert_to_draft", "created_at": "2029-12-31T21:00:00Z"}
READY_AGAIN = {"event": "ready_for_review", "created_at": "2029-12-31T22:00:00Z"}
SHARED = "actor `moshez` is the shared agent account; check the workers' rounds"


def pushed(listed: object, branch: str = "branch-1") -> tuple[world.World, object]:
    """Push branch-1 of a held world to a repository where GitHub lists PRs.

    Args:
        listed: the PRs GitHub lists for the branch ``branch``.
        branch: the branch the list is for.

    Returns:
        The world, and what the push did.
    """
    here = waiting_world(1)
    remote_to(here, "elsewhere", OTHER_URL)
    here.bodies[PULLS.format(branch=branch)] = listed
    return here, push(here, "elsewhere", "branch-1")


class TestPushToDraft(unittest.TestCase):
    """``pitboss push`` without ``--draft`` under pressure."""

    def test_an_open_draft_is_not_held(self) -> None:
        """The PR is a draft on GitHub: it goes out, says so and records no hold."""
        here, result = pushed([{"draft": True}])
        assert isinstance(result, world.Result)
        assert_that((result.code, pushes(here), lines(here)), equal_to((0, 1, [])))
        assert_that(result.out, equal_to(f"{FREE}\npushed\n"))

    def test_no_pull_request_is_held(self) -> None:
        """A branch with no open PR is held as before."""
        here, result = pushed([])
        assert isinstance(result, world.Result)
        assert_that((result.code, pushes(here)), equal_to((1, 0)))
        assert_that(result.out, contains_string(HELD))

    def test_a_ready_pull_request_is_held(self) -> None:
        """A PR that is not a draft is held as before."""
        here, result = pushed([{"draft": False}])
        assert isinstance(result, world.Result)
        assert_that((result.code, pushes(here)), equal_to((1, 0)))
        assert_that(result.out, contains_string(HELD))

    def test_the_draft_of_another_branch_is_held(self) -> None:
        """Only the PR of the pushed branch frees the push."""
        here, result = pushed([{"draft": True}], "branch-2")
        assert isinstance(result, world.Result)
        assert_that((result.code, pushes(here)), equal_to((1, 0)))

    def test_a_list_that_is_no_list_is_held(self) -> None:
        """An answer that is not a list of PRs frees nothing."""
        here, result = pushed({"draft": True})
        assert isinstance(result, world.Result)
        assert_that((result.code, pushes(here)), equal_to((1, 0)))


class TestBranches(unittest.TestCase):
    """The branches a push pushes, from git's arguments."""

    def test_refspecs_and_the_current_branch(self) -> None:
        """No refspec and HEAD mean the current branch; a pair means its target."""
        found = [
            pushdraft.branches(each, "now")
            for each in (
                ["origin"],
                ["--force", "origin", "HEAD"],
                ["origin", "+a:refs/heads/b", "c"],
                ["origin", "HEAD"],
            )
        ]
        assert_that(
            found,
            equal_to([["now"], ["now"], ["b", "c"], ["now"]]),
        )

    def test_a_detached_head_names_no_branch(self) -> None:
        """With no current branch there is nothing to ask GitHub."""
        assert_that(pushdraft.branches(["origin"], ""), equal_to([]))


def timeline(*events: object) -> world.World:
    """A world whose PR 2 has a timeline.

    Args:
        *events: its events.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[fakes.page(f"{world.PROJECT}/issues/2/timeline")] = list(events)
    return here


def told(here: world.World) -> Sequence[str]:
    """The draft-state lines of a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return [
        each for each in sweep(here).out.splitlines() if each.startswith("DRAFT STATE")
    ]


class TestDraftMoves(unittest.TestCase):
    """A draft-state change after the sweep marked the PR ready."""

    def test_a_conversion_after_ready_is_told(self) -> None:
        """The line names the event, its time and the shared account."""
        found = told(timeline(READY, CONVERTED))
        expected = (
            "DRAFT STATE CHANGED owner/project#2: convert_to_draft at"
            " 2029-12-31T21:00:00Z came after the sweep marked the PR ready; "
        )
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string(expected))
        assert_that(found[0], contains_string(SHARED))

    def test_the_newest_change_is_told(self) -> None:
        """A second marking after a conversion is the one told."""
        found = told(timeline(READY, CONVERTED, READY_AGAIN))
        assert_that(found[0], contains_string("ready_for_review at 2029-12-31T22"))

    def test_the_sweeps_own_marking_is_not_told(self) -> None:
        """A PR marked ready once, or never, says nothing."""
        assert_that([told(timeline(READY)), told(timeline())], equal_to([[], []]))

    def test_a_conversion_before_the_marking_is_not_told(self) -> None:
        """Only what came after the sweep's marking counts."""
        assert_that(told(timeline(CONVERTED, READY)), equal_to([]))

    def test_the_events_of_a_timeline(self) -> None:
        """The same decision, on events alone."""
        make = shapes.TimelineEvent
        events = [make(kind="ready_for_review", at="a"), make(kind="labeled", at="b")]
        assert_that(draftmoves.after_marked_ready(events), equal_to(None))
