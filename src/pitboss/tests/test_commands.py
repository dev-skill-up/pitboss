"""End-to-end tests of the commands but ``slots``: a fake GitHub, real git."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import fakes, world

CANCEL = f"POST {world.PROJECT}/actions/runs/11/cancel"
OPEN_PULLS = world.project_page("pulls?state=open")
SWEEP_LINES = (
    "UNREADABLE owner/gone: gh: not found",
    "owner/project#1 [dirty] auto-merge=off pending=0 failed=[test (job 8)]",
    "CONFLICT owner/project#1: merge main into branch-1",
    "FAILED owner/project#1: test: failed step",
    "READY TO MERGE owner/project#2",
    "queue=in_progress",
    "AUTO MERGE OFF owner/project#3",
    "MERGE BY HAND owner/lib#4",
    "RUNNER PRESSURE: 1 queue-run jobs",
    "STALE QUEUE RUN owner/project 11 (pr-2, queued)",
    "QUEUE RUN owner/project 12 (pr-2, in_progress): 48 of 60 minutes",
    "fetch failed in {workspace}/broken",
    "STRAGGLER {workspace}/project [main] uncommitted=1",
    "STALE WORKTREE {workspace}/merged-work [merged-work] (its PR merged)",
    "SWEEP REMINDER: Is any ticket closeable?",
    "EMPTY SLOT: tiny (small)",
    "SLOTS FREE 2: ",
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

    Args:
        here: the world.

    Returns:
        What the sweep did.
    """
    return world.again(here, "sweep", "--now", world.FUTURE)


def failed_line(here: world.World) -> str:
    """The FAILED line of the first PR in a sweep.

    Args:
        here: the world.

    Returns:
        The line.
    """
    return [x for x in sweep(here).out.splitlines() if x.startswith("FAILED")][0]


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
        world.invoke(here, *task)


def clear_queue(here: world.World) -> None:
    """Leave no open PR and no labelled ticket in a world.

    Args:
        here: the world.
    """
    for key in list(here.bodies):
        if "issues?state=open&labels=" in key:
            here.bodies[key] = []
    here.bodies[OPEN_PULLS] = []


class TestSweep(unittest.TestCase):
    """The sweep and the pressure check."""

    def test_sweep(self) -> None:
        """The sweep reports every section and exits 1 on a red or conflicted PR."""
        here = world.make_world()
        fakes.write(here.clone / "scratch", "unsaved")
        fakes.make_unfetchable(here.workspace, "broken")
        result = sweep(here)
        found = (
            missing(result.out, SWEEP_LINES, here),
            missing(result.err, SWEEP_ERRORS, here),
        )
        assert_that((found, result.code), equal_to((([], []), 1)))

    def test_sweep_says_why(self) -> None:
        """A failed check's line says its failed step, output and annotations."""
        expected = (
            "FAILED owner/project#1: test: failed step 'Run bats check'"
            " | check failed | 1 error | src/a.bats:3: bad type"
        )
        assert_that(failed_line(world.make_world()), equal_to(expected))

    def test_sweep_says_nothing_when_nothing_is_read(self) -> None:
        """A failed check GitHub answers nothing for is named alone."""
        here = world.make_world()
        for path in (world.RED_JOB, world.RED_RUN, world.RED_NOTES):
            del here.bodies[path]
        assert_that(failed_line(here), equal_to("FAILED owner/project#1: test"))

    def test_sweep_healthy(self) -> None:
        """With no red or conflicted PR the sweep exits 0."""
        here = world.make_world()
        here.bodies[OPEN_PULLS] = [{"number": 2}]
        assert_that(sweep(here).code, equal_to(0))

    def test_slots_free(self) -> None:
        """Free slots with work queued print SLOTS FREE n; busy or empty, none."""
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
        expected = [["SLOTS FREE 2: "], ["SLOTS FREE 1: "], [], []]
        assert_that(found, equal_to(expected))

    def test_unreadable_project(self) -> None:
        """A project the session cannot read stops the command."""
        here = world.make_world()
        del here.bodies[world.PROJECT]
        result = world.again(here, "pressure")
        assert_that(result.code, equal_to("cannot read owner/project"))


class TestChanges(unittest.TestCase):
    """The commands that change something, dry and not."""

    def test_cancel_stale_runs(self) -> None:
        """Stale runs are cancelled only with --no-dry-run; a refusal is reported."""
        here = world.make_world()
        dry = world.again(here, "cancel-stale-runs")
        posts = [call for call in here.calls if "POST" in call]
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
