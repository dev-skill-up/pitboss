"""B2, B6, B9, B10, B22, B23 and D1 to D11: what ``slots next`` offers and says.

The orchestrator reads the whole list and fills a free slot in the same turn
(keyword: skip-item), dispatches from saved briefs (keyword: brief-save), ranks
mechanical relock reviews last (keyword: relock-last), offers no step to a PR
that is blocked (keyword: blocked-body), says a stuck run and a duplicate PR
(keywords: stuck-ci, duplicate-pr), and says what decided an UNKNOWN so that it
can be overridden (keywords: unknown-data, force-brief, quiesce); pitboss#444.
"""

import argparse
import dataclasses
import datetime
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import (
    briefsave,
    duplicatepr,
    parsing,
    pulls,
    shapes,
    skipitem,
    steps,
    stuckci,
    work,
)
from . import fakes, rankworld, world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import lacks, says
from .rankworld import (
    fixing,
    lines_are,
    mentioning,
    next_output,
    starts,
)
from .fastvariants import named
from .fastworld import NINTH, fast_world, listed
from .test_work import NONE, REPO, facts, item, stepped
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


class TestSkip(unittest.TestCase):
    """B2: ``--skip`` takes an item out of the list for this run."""

    def test_b2_a_skipped_item_is_left_out_and_said(self) -> None:
        """The next item is the one the list starts; a SKIPPED line says so."""
        here = world.make_world()
        plain = starts(here)
        done = listed(here, "--skip", "owner/project#1")
        skipped = rankworld.NEXT_LINE.findall(done.out)
        assert_that("owner/project#1" in plain, equal_to(True))
        left = [each for each in plain if each != "owner/project#1"]
        assert_that(skipped, equal_to(left))
        lines_are(
            done.out,
            "SKIPPED:",
            ["SKIPPED: owner/project#1 is left out of this list by --skip"],
        )
        lacks(done.out, "DISPATCH: owner/project#1")

    def test_b2_a_bare_number_and_a_repeat_name_items_and_others_are_silent(
        self,
    ) -> None:
        """``#3`` is of the project; an item the list does not hold says nothing."""
        here = world.make_world()
        done = listed(here, "--skip", "#3", "--skip", "owner/project#77")
        said = [each for each in done.out.splitlines() if each.startswith("SKIPPED")]
        same(said, ["SKIPPED: owner/project#3 is left out of this list by --skip"])

    def test_b2_items_without_the_skipped_ones_keep_their_order(self) -> None:
        """Items without the skipped ones; no skip is no line and no change."""
        offer = work.Offered(
            items=[
                item("owner/project#1", work.Category.REVIEW),
                item("owner/project#2", work.Category.REVIEW),
            ],
            held=[],
            standing={},
            blocked=[],
        )
        two = skipitem.without(offer, ["owner/project#1"])
        same({each.reference for each in two.items}, {"owner/project#2"})
        same(skipitem.lines(offer, []), [])
        same(skipitem.named(argparse.Namespace(), REPO), [])


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

    def test_b6_the_brief_of_one_item_is_saved_and_the_line_is_on_standard_error(
        self,
    ) -> None:
        """Standard output stays the brief alone."""
        here = with_pull_issues(fast_world())
        found = one(here, NINTH)
        same(found.code, 0)
        lacks(found.out, "DISPATCH")
        says(found.err, "DISPATCH: owner/project#9", "brief saved to")
        same(briefs_of(here), ["owner-project-9.brief"])

    def test_b6_force_prints_and_saves_the_brief_of_an_item_answered_unknown(
        self,
    ) -> None:
        """Plain: UNKNOWN and no file. ``--force``: the brief, its file and the line."""
        here = with_pull_issues(named())
        plain = one(here, NINTH)
        same((plain.code, plain.out, briefs_of(here)), (1, "", []))
        forced = one(here, NINTH, "--force")
        same(forced.code, 0)
        assert_that(len(forced.out) > 0, equal_to(True))
        says(
            forced.err, "FORCED: the plain command refuses", "DISPATCH: owner/project#9"
        )
        same(briefs_of(here), ["owner-project-9.brief"])
        saved = here.ledger.parent / briefsave.DIRECTORY / "owner-project-9.brief"
        assert_that(saved.read_text().strip() in forced.out, equal_to(True))

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


def order_of(*every: work.Item) -> Sequence[str]:
    """The references of the items, ordered.

    Args:
        *every: the items.

    Returns:
        The references.
    """
    return tuple(each.reference for each in work.ordered(list(every), []))


class TestRelockLast(unittest.TestCase):
    """B9: the review of a relock PR ranks after the other work."""

    def test_b9_a_relock_review_is_last(self) -> None:
        """Even oldest, it stands after another PR and a ticket."""
        new = item("owner/project#9", work.Category.NEW_PR)
        pulled = work.pull_items([relocking(), facts(3, NONE)])
        same(
            order_of(*pulled, new),
            ("owner/project#3", "owner/project#9", "owner/project#2"),
        )

    def test_b9_a_relock_pr_at_another_step_keeps_its_place(self) -> None:
        """The nearest input it must still keep first: a relock PR to fix."""
        fix = relocking(steps.worker(steps.Task.FIX_CI))
        pulled = work.pull_items([facts(3, NONE), fix])
        same(order_of(*pulled), ("owner/project#2", "owner/project#3"))


def blocked(line: str, state: str = "open") -> world.World:
    """A world where PR 3 fixes ticket 9 and its body has a line.

    Args:
        line: the line the body has.
        state: the state of ``owner/lib#3``.

    Returns:
        The world.
    """
    here = rankworld.depends_world("")
    fixing(here, 3, f"Fixes #9\n\n{line}")
    here.bodies[rankworld.BLOCKER] = {**rankworld.LIB_THREE, "state": state}
    rankworld.serve(here, "owner/project", 9, rankworld.ticket())
    return here


class TestBlockedBody(unittest.TestCase):
    """B10: a PR whose body says it is blocked on a ticket is not offered a step."""

    def test_b10_a_pr_blocked_on_another_ticket_has_no_step(self) -> None:
        """``Blocked on`` and ``Blocked by`` in the PR's body: BLOCKED, no PR STATE."""
        for line in ("Blocked on owner/lib#3", "blocked by owner/lib#3"):
            with self.subTest(line):
                output = next_output(blocked(line))
                lines_are(output, "BLOCKED", ["BLOCKED owner/project#3 by owner/lib#3"])
                rankworld.absent(output, "PR STATE owner/project#3")

    def test_b10_a_closed_blocker_or_its_own_ticket_blocks_nothing(self) -> None:
        """The nearest inputs it must still pass: closed, and the PR's own ticket."""
        for line, state in (
            ("Blocked on owner/lib#3", "closed"),
            ("Blocked on #9", "open"),
        ):
            with self.subTest(line, state=state):
                output = next_output(blocked(line, state))
                lines_are(output, "BLOCKED", [])


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
        waiting_pr = stepped(facts(3, NONE), steps.wait_for_ci())
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


class TestDuplicate(unittest.TestCase):
    """B23: two open PRs on one ticket are named."""

    def test_b23_two_prs_on_one_ticket_are_named_oldest_first(self) -> None:
        """Both fix ticket 9; the older is named first."""
        first = facts(3, NONE, body="Fixes #9", created_at="2026-11-01T00:00:00Z")
        second = facts(4, NONE, body="Fixes #9", created_at="2026-11-02T00:00:00Z")
        lines = duplicatepr.lines([second, first])
        same(
            lines,
            [
                "DUPLICATE PR: owner/project#3 and owner/project#4 work ticket"
                " owner/project#9; step: close the newer as a duplicate"
            ],
        )

    def test_b23_one_pr_on_each_ticket_names_nothing(self) -> None:
        """The nearest input it must still pass; one PR twice is one PR."""
        one_pr = facts(3, NONE, body="Fixes #9\n\nFixes #9")
        other = facts(4, NONE, body="Fixes #8")
        same(duplicatepr.lines([one_pr, other]), [])

    def test_b23_slots_next_prints_the_line(self) -> None:
        """Two PRs of the world that fix ticket 9."""
        here = world.make_world()
        fixing(here, 2, "Fixes #9")
        fixing(here, 3, "Fixes #9")
        found = mentioning(listed(here).out, "DUPLICATE PR")
        same(len(found), 1)
        says(found[0], "work ticket owner/project#9", "close the newer")
