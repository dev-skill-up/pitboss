"""B2, B6, B9, B10, B22, B23 and D1 to D11: what ``slots next`` offers and says.

The orchestrator reads the whole list and fills a free slot in the same turn
(keyword: skip-item), dispatches from saved briefs (keyword: brief-save), ranks
mechanical relock reviews last (keyword: relock-last), offers no step to a PR
that is blocked (keyword: blocked-body), says a stuck run and a duplicate PR
(keywords: stuck-ci, duplicate-pr), and says what decided an UNKNOWN so that it
can be overridden (keywords: unknown-data, force-brief, quiesce); pitboss#444.
"""

import dataclasses
import datetime
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import briefsave, parsing, pulls, shapes, steps, stuckci
from . import fakes, world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import lacks, says
from .rankworld import mentioning
from .fastworld import NINTH, fast_world, listed
from .test_work import NONE, facts, stepped
from .fakes import write

NOW = datetime.datetime(2026, 11, 12, 12, 0, tzinfo=datetime.timezone.utc)


def briefs_of(here: world.World) -> Sequence[str]:
    """The names of the files in the brief directory beside the ledger.

    Args:
        here: the world.

    Returns:
        The names, sorted.
    """
    found = here.ledger.parent / briefsave.DIRECTORY
    return sorted(each.name for each in found.iterdir()) if found.exists() else []


class TestBriefs(unittest.TestCase):
    """B6: each brief is a file named from the item, and a line says so."""

    def test_b6_the_listed_briefs_are_saved_and_dispatch_lines_name_them(self) -> None:
        """A file for each brief, the brief itself, and the line with its path."""
        here = world.make_world()
        done = listed(here)
        dispatch = mentioning(done.out, "DISPATCH: ")
        assert_that(len(dispatch) > 0, equal_to(True))
        for line in dispatch:
            says(line, "brief saved to", "dispatch with that file")
        names = briefs_of(here)
        assert_that("owner-project-3.brief" in names, equal_to(True))
        saved = (here.ledger.parent / "briefs" / "owner-project-3.brief").read_text()
        assert_that(saved.strip() in done.out, equal_to(True))

    def test_b6_a_brief_that_cannot_be_written_says_so(self) -> None:
        """The directory is a file: the line says NOT saved and why."""
        directory = fakes.directory()
        write(directory / briefsave.DIRECTORY, "in the way")
        line = briefsave.save(directory / "ledger.json", "o/r#1", "small", "text")
        says(line, "DISPATCH: o/r#1: brief NOT saved", "do not hand-build one")
        same(briefsave.name_of("owner/lib#12"), "owner-lib-12.brief")


def relocking(*step: steps.Next) -> pulls.PullFacts:
    """The oldest PR, a relock PR, at a step (the review when none is given).

    Args:
        *step: the step to give it, if any.

    Returns:
        The PR.
    """
    oldest = facts(2, NONE, created_at="2026-01-01T00:00:00+00:00")
    relock = dataclasses.replace(oldest, relock=True)
    return stepped(relock, step[0]) if step else relock


def run_of(number: int, status: str, minute: int) -> shapes.WorkflowRun:
    """A run created some minutes before now, as the API lists it.

    Args:
        number: its id.
        status: its status.
        minute: minutes before now.

    Returns:
        The run.
    """
    page = json.dumps({"workflow_runs": [_run_json(number, status, minute)]})
    return parsing.workflow_runs(page)[0]


def stuck_among(
    queued: shapes.WorkflowRun, other: shapes.WorkflowRun
) -> Sequence[tuple[shapes.WorkflowRun, int, int]]:
    """The stuck runs among a queued run and another.

    Args:
        queued: the run that may be stuck.
        other: another run of the same project.

    Returns:
        What ``stuckci.stuck`` finds, at the fixed time.
    """
    return stuckci.stuck([queued], [queued, other], NOW)


class TestStuckRun(unittest.TestCase):
    """B22: a run queued for long while later runs finished gets a diagnosis."""

    def test_b22_a_queued_run_with_later_completed_runs_is_stuck(self) -> None:
        """Queued over the limit and a later run completed."""
        queued = run_of(1, "queued", 120)
        later = run_of(2, "completed", 60)
        found = stuck_among(queued, later)
        same([(each[0].id, each[1], each[2]) for each in found], [(1, 120, 1)])
        text = stuckci.warning("o/r", 7, "a" * 40, found[0])
        says(text, "STUCK CI o/r#7: run 1 queued 120 minutes", "1 later runs")
        says(text, "gh api repos/o/r/actions/runs?head_sha=", "re-run it")
        lacks(text, "no re-run")

    def test_b22_a_recent_run_or_one_without_later_runs_is_not_stuck(self) -> None:
        """The nearest inputs it must still pass."""
        fresh = run_of(1, "queued", stuckci.MINUTES - 1)
        later = run_of(2, "completed", 0)
        old = run_of(3, "queued", 120)
        earlier = run_of(4, "completed", 200)
        running = run_of(5, "in_progress", 120)
        same(stuck_among(fresh, later), [])
        same(stuck_among(old, earlier), [])
        same(stuck_among(running, later), [])

    def test_b22_only_a_pr_waiting_for_ci_is_read(self) -> None:
        """The runs are read for a PR at the wait; a read that fails says nothing."""
        waiting_pr = stepped(facts(3, NONE), steps.ci_pending())
        reviewing = facts(4, NONE)
        head = waiting_pr.pull.head.sha
        old = _run_json(1, "queued", 120)
        new = _run_json(2, "completed", 10)
        mine = fakes.page(f"repos/owner/project/actions/runs?head_sha={head}")
        every = fakes.page("repos/owner/project/actions/runs")
        github = fakes.github(
            {mine: {"workflow_runs": [old]}, every: {"workflow_runs": [old, new]}}
        )
        said = stuckci.lines(github, [waiting_pr, reviewing], NOW)
        same(len(said), 1)
        assert_that(said[0], contains_string("STUCK CI owner/project#3: run 1"))
        same(stuckci.lines(fakes.github({}), [waiting_pr], NOW), [])


def _run_json(number: int, status: str, minute: int) -> dict[str, object]:
    created = NOW - datetime.timedelta(minutes=minute)
    return {
        "id": number,
        "status": status,
        "conclusion": None,
        "created_at": created.isoformat(),
        "head_branch": "b",
    }
