"""A push to the branch of a draft PR is free; a changed draft state is told (#355)."""

import re
import pathlib
import tempfile
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import draftmoves, pushdraft, shapes
from . import fakes, world
from .test_commands import sweep

OTHER_URL = "git@github.com:other/repo.git"
PULLS = "repos/other/repo/pulls?head=other:{branch}&state=open"
JOBS = world.project_page("actions/runs/11/jobs")
HELD = "RUNNER PRESSURE"
FREE = "the open PR of branch-1 is a draft: a push to a draft is never held"
DRAFT_LINE = re.compile(r"^DRAFT STATE.*$", re.MULTILINE)
SHARED = "actor `moshez` is the shared agent account; check the workers' rounds"


def held_world(listed: object, branch: str) -> world.World:
    """A world with a job waiting for a runner, whose remote GitHub lists PRs for.

    Args:
        listed: the PRs GitHub lists for the branch ``branch``.
        branch: the branch the list is for.

    Returns:
        The world; its remote ``elsewhere`` names another repository.
    """
    here = world.make_world()
    here.bodies[JOBS] = {"jobs": [{"status": "queued"}]}
    here.bodies[PULLS.format(branch=branch)] = listed
    fakes.run_git(here.clone, "branch", "-f", "branch-1")
    fakes.run_git(here.clone, "remote", "add", "elsewhere", OTHER_URL)
    target = str(world.origin_of(here.clone))
    fakes.run_git(here.clone, "config", "remote.elsewhere.pushurl", target)
    return here


def pushed(here: world.World) -> world.Result:
    """Push branch-1 to the remote of a world, without ``--draft``.

    Args:
        here: the world.

    Returns:
        What the push did.
    """
    when = world.START.isoformat()
    return world.again(
        here, "push", "--now", when, "--no-dry-run", "elsewhere", "branch-1"
    )


def gits(here: world.World) -> int:
    """How many times a world ran ``git push``.

    Args:
        here: the world.

    Returns:
        The count.
    """
    return sum(list(each[:2]) == ["git", "push"] for each in here.calls)


class TestPushToDraft(unittest.TestCase):
    """``pitboss push`` without ``--draft`` under pressure."""

    def test_an_open_draft_is_not_held(self) -> None:
        """The PR is a draft on GitHub: it goes out and records no hold."""
        here = held_world([{"draft": True}], "branch-1")
        result = pushed(here)
        record = here.clone / ".git" / "pitboss-pressure.log"
        assert_that((result.code, gits(here), record.exists()), equal_to((0, 1, False)))
        assert_that(result.out, equal_to(f"{FREE}\npushed\n"))

    def test_every_other_answer_is_held(self) -> None:
        """No PR, a ready PR, a draft of another branch, a non-list: held as before."""
        cases = [
            ([], "branch-1"),
            ([{"draft": False}], "branch-1"),
            ([{"draft": True}], "branch-2"),
            ({"draft": True}, "branch-1"),
        ]
        found = []
        for listed, branch in cases:
            here = held_world(listed, branch)
            result = pushed(here)
            found.append((result.code, gits(here), HELD in result.out))
        assert_that(found, equal_to([(1, 0, True)] * len(cases)))


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
            )
        ]
        assert_that(found, equal_to([["now"], ["now"], ["b", "c"]]))

    def test_a_detached_head_names_no_branch(self) -> None:
        """With no current branch there is nothing to ask GitHub."""
        assert_that(pushdraft.branches(["origin"], ""), equal_to([]))


def event(kind: str, hour: int) -> Mapping[str, str]:
    """A timeline event of the day before the tests' sweep.

    Args:
        kind: GitHub's event name.
        hour: the hour of 2029-12-31.

    Returns:
        The event's JSON.
    """
    return {"event": kind, "created_at": f"2029-12-31T{hour:02}:00:00Z"}


def told(*events: Mapping[str, str]) -> Sequence[str]:
    """The draft-state lines of a sweep of a world whose PR 3 has a timeline.

    Args:
        *events: the timeline of PR 3.

    Returns:
        The lines.
    """
    here = world.make_world()
    timeline = [("issues/3/timeline", list(events))]
    here.bodies.update(fakes.bodies_under(world.PROJECT, timeline))
    return DRAFT_LINE.findall(sweep(here).out)


class TestDraftMoves(unittest.TestCase):
    """A draft-state change after the sweep marked the PR ready."""

    def test_a_conversion_after_ready_is_told(self) -> None:
        """The line names the event, its time and the shared account."""
        found = told(event("ready_for_review", 20), event("convert_to_draft", 21))
        expected = (
            "DRAFT STATE CHANGED owner/project#3: convert_to_draft at"
            " 2029-12-31T21:00:00Z came after the sweep marked the PR ready; "
        )
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string(expected))
        assert_that(found[0], contains_string(SHARED))

    def test_the_newest_change_is_told(self) -> None:
        """A second marking after a conversion is the one told."""
        found = told(
            event("ready_for_review", 20),
            event("convert_to_draft", 21),
            event("ready_for_review", 22),
        )
        assert_that(found[0], contains_string("ready_for_review at 2029-12-31T22"))

    def test_nothing_after_the_marking_is_not_told(self) -> None:
        """A PR marked ready once, never marked, or converted first says nothing."""
        found = [
            told(event("ready_for_review", 20)),
            told(),
            told(event("convert_to_draft", 20), event("ready_for_review", 21)),
        ]
        assert_that(found, equal_to([[], [], []]))

    def test_the_events_of_a_timeline(self) -> None:
        """Events of other kinds after the marking are not changes of state."""
        make = shapes.TimelineEvent
        events = [make(kind="ready_for_review", at="a"), make(kind="labeled", at="b")]
        assert_that(draftmoves.after_marked_ready(events), equal_to(None))


class TestFailures(unittest.TestCase):
    """What cannot be read says nothing, or names no branch."""

    def test_an_unreadable_timeline_says_nothing(self) -> None:
        """The failed call is not a draft-state change."""
        refused = fakes.github(
            {fakes.page("repos/o/r/issues/3/timeline"): fakes.REFUSED}
        )
        assert_that(draftmoves.tell(refused, "o/r", 3), equal_to([]))

    def test_a_failing_git_names_no_branch(self) -> None:
        """No branch is told, so nothing is asked of GitHub."""
        with tempfile.TemporaryDirectory() as empty:
            run = fakes.FakeProcesses(bodies={}, cwd=pathlib.Path(empty))
            assert_that(pushdraft.current_branch(run), equal_to(""))
