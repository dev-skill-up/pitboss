"""A push to the branch of a draft PR is free; a changed draft state is told (#355)."""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import pushdraft
from . import fakes, world
from .test_commands import sweep
from .pushworld import elsewhere

OTHER_URL = "git@github.com:owner/other.git"
PULLS = "repos/owner/other/pulls?head=owner:{branch}&state=open"
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
    elsewhere(here, OTHER_URL)
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
