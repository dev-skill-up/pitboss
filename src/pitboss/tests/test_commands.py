"""End-to-end tests of the commands but ``slots``: a fake GitHub, real git."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import (
    cleanworld,
    fakes,
    liveagents,
    orphans,
    ownerbodies,
    quietworld,
    syncworld,
    world,
)
from .says import exits
from .fakes import calls_with

CANCEL = f"POST {world.PROJECT}/actions/runs/11/cancel"
OPEN_PULLS = world.project_page("pulls?state=open")
JOBS_FAILED = "owner/project#2: jobs answered HTTP 404"
QUEUE_CALL_FAILS = (
    ["partial: 1 queue run(s) not counted", f"UNREADABLE {JOBS_FAILED}"],
    0,
    JOBS_FAILED,
)
SWEEP_LINES = (
    "owner/project#1 [dirty] auto-merge=off pending=0 failed=[test (job 8)]",
    "WORKER: owner/project#1: resolve the conflict",
    "queue=in_progress",
    "RUNNER PRESSURE: 1 queue-run jobs",
    "STALE QUEUE RUN owner/project 11 (pr-2, queued)",
    "QUEUE RUN owner/project 12 (pr-2, in_progress): 48 of 60 minutes",
    "fetch failed in {workspace}/broken",
    "STRAGGLER {workspace}/project [main] uncommitted=1",
    "STALE WORKTREE {workspace}/merged-work [merged-work] (its PR merged)",
    "SWEEP REMINDER: Is any ticket closeable?",
    "EMPTY SLOT: tiny (small)",
    "SLOTS FREE: 2",
)
CANCEL_LINES = (
    "CANCELLED STALE QUEUE RUN owner/project 11 (dry run",
    "CANCELLED STALE QUEUE RUN owner/project 11\n",
    "COULD NOT CANCEL STALE QUEUE RUN owner/project 11",
)
CLEAN_LINES = (
    "(its PR merged) (dry run",
    "COULD NOT REMOVE WORKTREE {workspace}/merged-work",
    "REMOVED WORKTREE {workspace}/merged-work (its PR merged)\n",
)


def missing(text: str, expected: Sequence[str], here: world.World) -> Sequence[str]:
    """The expected pieces that are not in the text.

    Args:
        text: the output.
        expected: the pieces, with ``{workspace}`` for the world's workspace.
        here: the world.

    Returns:
        The missing pieces.
    """
    pieces = [piece.format(workspace=here.workspace) for piece in expected]
    return [piece for piece in pieces if piece not in text]


REVIEW_FORMS = [
    ("gated", ["# owner/gated: gated", "ASCII only", "Reviewed: {{sha}}"], []),
    ("other/lib", ["# other/lib: not gated", "ASCII only"], ["ASCII only"]),
]
SWEEP_ERRORS = ("CHECK BEFORE YOU ANSWER", "] checkouts done")
REMOVING = ("--now", world.FUTURE, "--no-dry-run")


def sweep(here: world.World) -> world.Result:
    """Sweep a world at a time after everything in it.

    The agents the ledger holds are the ones that run (pitboss#94).

    Args:
        here: the world.

    Returns:
        What the sweep did.
    """
    return world.again(here, "sweep", "--now", world.FUTURE, *liveagents.running(here))


def unclean_third(here: world.World) -> None:
    """Make PR 3 healthy but not clean, so only an approved head is told to arm.

    Args:
        here: the world.
    """
    here.bodies[f"{world.PROJECT}/pulls/3"] = fakes.pull_body(
        3, head={"sha": "3" * 40, "ref": "branch-3"}, mergeable_state="has_hooks"
    )


def reviewed_third(reviewed: str | None) -> world.World:
    """A world whose PR 3 is healthy, not clean, with a review of a head.

    Args:
        reviewed: the head the review names, None for no review.

    Returns:
        The world; PR 3's head is a fix on top of the commit of ``4`` * 40.
    """
    head = "3" * 40
    fix = {"sha": "3", "parents": [{"sha": "2"}]}
    here = world.make_world()
    unclean_third(here)
    compare = f"{world.PROJECT}/compare/main..."
    here.bodies[compare + head] = {"commits": [fix]}
    here.bodies[compare + "4" * 40] = {"commits": []}
    if reviewed:
        runs = world.project_page(f"commits/{reviewed}/check-runs")
        here.bodies.setdefault(runs, {"check_runs": []})
        body = f"## Review\nReviewed: {reviewed}\nVerdict: approved\n"
        comments = world.project_page("issues/3/comments")
        here.bodies[comments] = [dict(world.COMMENT, body=body)]
    return quietworld.calm(here)


def free_lines(result: world.Result) -> Sequence[str]:
    """The SLOTS FREE lines of a sweep, cut after the count.

    Args:
        result: what the sweep did.

    Returns:
        The lines.
    """
    lines = [x for x in result.out.splitlines() if x.startswith("SLOTS FREE")]
    return [line.split(":")[0] + ": " for line in lines]


def occupy(here: world.World, slot_names: Sequence[str]) -> None:
    """Put an agent in each named slot.

    Args:
        here: the world.
        slot_names: the slots.
    """
    for each in slot_names:
        task = ("slots", "set", here.config, each, f"agent-{each}", "#9")
        world.invoke(here, *task, "--running", f"agent-{each}")


def clear_queue(here: world.World) -> None:
    """Leave no open PR and no labelled ticket in a world.

    Args:
        here: the world.
    """
    for key in list(here.bodies):
        if "issues?state=open&labels=" in key:
            here.bodies[key] = []
    here.bodies[OPEN_PULLS] = []


def third_line(out: str) -> str:
    """PR 3's line of the sweep.

    Args:
        out: what the sweep printed.

    Returns:
        The line that starts with PR 3.
    """
    return "".join(x for x in out.splitlines() if x.startswith("owner/project#3 "))


class TestSweep(unittest.TestCase):
    """The sweep and the pressure check."""

    def test_sweep(self) -> None:
        """The sweep reports every section and exits 1 on a red or conflicted PR."""
        here = world.make_world()
        cleanworld.only_list_worktrees(here)
        fakes.write(here.clone / "scratch", "unsaved")
        fakes.make_unfetchable(here.workspace, "broken")
        result = sweep(here)
        found = (
            missing(result.out, SWEEP_LINES, here),
            missing(result.err, SWEEP_ERRORS, here),
        )
        assert_that((found, result.code), equal_to((([], []), 1)))

    def test_sweep_names_an_orphaned_checkout(self) -> None:
        """A worktree whose main checkout is gone is named, not a traceback (#98)."""
        here = syncworld.make_synced().here
        here.bodies[OPEN_PULLS] = [{"number": 2}]
        orphans.make_orphaned(here.workspace, "orphan-98")
        result = sweep(here)
        expected = f"ORPHANED CHECKOUT {here.workspace}/orphan-98"
        found = (expected in result.out, "Traceback" in result.err, result.code)
        assert_that(found, equal_to((True, False, 0)))

    def test_sweep_fails_when_a_read_is_answered_with_an_error(self) -> None:
        """A PR's read GitHub answers 404: no decision on a partial world."""
        here = quietworld.calm(syncworld.make_synced().here)
        here.bodies[OPEN_PULLS] = [{"number": 1}, {"number": 2}]
        world.unread_first(here)
        result = sweep(here)
        found = (
            "READ FAILED: repos/owner/project/commits/" in result.err,
            "NEXT " in result.out,
            "Traceback" in result.err,
            result.code,
        )
        assert_that(found, equal_to((True, False, False, 1)))

    def test_sweep_goes_on_when_a_queue_run_call_fails(self) -> None:
        """A queue run whose jobs call fails is named and the sweep goes on (#101)."""
        here = syncworld.make_synced().here
        here.bodies[OPEN_PULLS] = [{"number": 2}]
        del here.bodies[world.project_page("actions/runs/11/jobs")]
        result = sweep(here)
        lines = result.out.splitlines()
        pressure = world.again(here, "pressure").code  # a failed call is no free runner
        found = [x.rsplit("; ", 1)[-1] for x in lines if "partial" in x]
        found += [x for x in lines if "jobs answered" in x]
        assert_that((found, result.code, pressure), equal_to(QUEUE_CALL_FAILS))

    def test_sweep_healthy(self) -> None:
        """With no red or conflicted PR the sweep exits 0."""
        here = syncworld.make_synced().here
        here.bodies[OPEN_PULLS] = [{"number": 2}]
        exits(sweep(here), 0)

    def test_a_review_counts_only_for_the_head_it_names(self) -> None:
        """No review and an older head's are not counted; the head's is (#85)."""
        found = [
            "review=approved-this-head" in third_line(sweep(reviewed_third(each)).out)
            for each in (None, "4" * 40, "3" * 40)
        ]
        assert_that(found, equal_to([False, False, True]))

    def test_slots_free(self) -> None:
        """Work prints SLOTS FREE, a datum of the answer; no work prints none."""
        found = []
        for taken, empty_queue in (
            ((), False),
            (("tiny",), False),
            (("tiny", "big"), False),
            (("tiny",), True),
        ):
            here = world.make_world()
            occupy(here, taken)
            if empty_queue:
                clear_queue(here)
            found.append(free_lines(sweep(here)))
        expected = [["SLOTS FREE: "]] * 3 + [[]]
        assert_that(found, equal_to(expected))

    def test_unreadable_project(self) -> None:
        """A project the owner's list lacks and the session cannot read stops it."""
        here = world.make_world()
        here.bodies[ownerbodies.LISTING] = ownerbodies.listing(("owner/lib", False))
        del here.bodies[world.PROJECT]
        result = world.again(here, "pressure")
        assert_that(result.code, equal_to("cannot read owner/project"))


class TestChanges(unittest.TestCase):
    """The commands that change something, dry and not."""

    def test_cancel_stale_runs(self) -> None:
        """Stale runs are cancelled only with --no-dry-run; a refusal is reported."""
        here = world.make_world()
        dry = world.again(here, "cancel-stale-runs")
        posts = calls_with(here.calls, "POST")
        outputs = [dry.out]
        for remove in [False, True]:
            if remove:
                del here.bodies[CANCEL]
            outputs.append(world.again(here, "cancel-stale-runs", "--no-dry-run").out)
        found = (posts, missing("".join(outputs), CANCEL_LINES, here))
        assert_that(found, equal_to(([], [])))

    def test_clean_worktrees(self) -> None:
        """Stale worktrees are removed only with --no-dry-run; a refusal is reported."""
        here = world.make_world()
        dry = world.again(here, "clean-worktrees", "--now", world.FUTURE)
        kept = here.worktree.exists()
        outputs = [dry.out]
        for lock in ["lock", "unlock"]:
            fakes.run_git(here.clone, "worktree", lock, str(here.worktree))
            outputs.append(world.again(here, "clean-worktrees", *REMOVING).out)
        found = (
            kept,
            here.worktree.exists(),
            missing("".join(outputs), CLEAN_LINES, here),
        )
        assert_that(found, equal_to((True, False, [])))

    def test_review_form(self) -> None:
        """The form is printed, with the gated rules for a gated repository."""
        here = world.make_world()
        found = [
            missing(world.again(here, "review-form", name).out, pieces, here)
            for name, pieces, _ in REVIEW_FORMS
        ]
        assert_that(found, equal_to([absent for _, _, absent in REVIEW_FORMS]))
