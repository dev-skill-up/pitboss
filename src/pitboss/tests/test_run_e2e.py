"""A changed e2e suite runs before any approval of a draft (pitboss#199).

The cause: a draft's CI runs plan and build only, so a draft that changes
``e2e/`` had no e2e result when its Execution was approved, and the owner's
ruling was given on a PR whose e2e suite was red.
"""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, dispatchruns, flow, markers, pullfiles, shapes, steps
from . import fakes, quietworld, test_flow, world
from .briefmake import make
from .exemptworld import HELD_WORDS, state_line
from .test_commands import sweep
from .test_flow import state
from .test_flow_sweep import APPROVED, HEAD, graded, world_with
from .test_slot_commands import next_output

LINE = "RUN E2E BEFORE APPROVAL: dispatch check.yml on branch-3"
QUERY = f"head_sha={HEAD}&event=workflow_dispatch&status=completed"
DISPATCHED = f"actions/workflows/check.yml/runs?{QUERY}"
ANY_WORKFLOW = f"actions/runs?{QUERY}"
PAGES = {
    "files": "pulls/3/files",
    "runs": f"commits/{HEAD}/check-runs",
    "dispatch": DISPATCHED,
    "any": ANY_WORKFLOW,
}
RAN, RUNNING = (
    {"id": 9, "name": "e2e", "status": status, "conclusion": conclusion}
    for status, conclusion in (("completed", "success"), ("in_progress", None))
)
NO_RUN: Sequence[Mapping[str, int]] = ()
DONE_RUN: Sequence[Mapping[str, int]] = ({"id": 5},)
E2E_FILE = {"filename": "e2e/reader.spec.js"}
MOVED = {"filename": "src/reader.js", "previous_filename": "e2e/reader.js"}
OTHER_FILE = {"filename": "src/reader.js"}
NOT_STARTED = "NOT STARTED: e2e has not run at"
WAITING = "waiting for CI at this head"


def served(here: world.World, page: str, body: object) -> world.World:
    """Serve a page of PR 3.

    Args:
        here: the world.
        page: ``files``, ``runs``, ``dispatch`` or ``any``.
        body: what GitHub gives for it.

    Returns:
        The same world.
    """
    here.bodies[fakes.page(f"{world.PROJECT}/{PAGES[page]}")] = body
    return here


def built(kind: brief.Kind, e2e: bool) -> str:
    """The brief of a kind, for a PR that changes the e2e suite or not.

    Args:
        kind: the kind.
        e2e: whether the PR changes what the e2e suite runs on.

    Returns:
        The text.
    """
    return brief.build(dataclasses.replace(make(kind), e2e=e2e))


def said(
    rounds: Sequence[shapes.Comment],
    changed: Sequence[Mapping[str, str]],
    *runs: Mapping[str, object],
    dispatch: Sequence[Mapping[str, int]] = NO_RUN,
) -> tuple[str, str]:
    """What the sweep prints and PR 3's PR STATE line, for a draft PR 3.

    Args:
        rounds: PR 3's comments.
        changed: the files its diff changes.
        *runs: the check runs of its head.
        dispatch: the completed dispatched runs of its head.

    Returns:
        The sweep's output, and the PR STATE line of PR 3.
    """
    here = served(world_with(rounds, draft=True), "files", list(changed))
    quietworld.unheld(here)
    served(here, "runs", {"check_runs": list(runs)})
    served(here, "dispatch", {"workflow_runs": list(dispatch)})
    lines = next_output(here).splitlines()
    found = "".join(each for each in lines if "PR STATE owner/project#3" in each)
    return sweep(here).out, found


APPROVED_PLAN = [graded(APPROVED, None, 1)]
APPROVED_REVIEW = test_flow.graded(test_flow.APPROVED, None, 1)
REJECTED_REVIEW = test_flow.graded(None, test_flow.CHANGES, 2)
# the Plan approved, the files changed, the check runs, the completed dispatched
# runs, and what the draft says
SWEEPS = {
    "a changed e2e and no check run": ([E2E_FILE], [], NO_RUN, f"next step: {LINE}"),
    "a rename out of e2e": ([MOVED], [], NO_RUN, f"next step: {LINE}"),
    "a draft run that skipped e2e (quire#1038)": (
        [E2E_FILE],
        [RAN],
        NO_RUN,
        f"next step: {LINE}",
    ),
    "a completed dispatched run of the head": (
        [E2E_FILE],
        [RAN],
        DONE_RUN,
        "next step: mark the PR ready",
    ),
    "a run that is running": (
        [E2E_FILE],
        [RUNNING],
        NO_RUN,
        f"next step: {WAITING}",
    ),
    "a change outside e2e": (
        [OTHER_FILE],
        [],
        NO_RUN,
        "next step: mark the PR ready",
    ),
}


class TestTheSweep(unittest.TestCase):
    """The sweep and ``slots next`` say to dispatch the check workflow."""

    def test_each_case_says_what_the_draft_needs(self) -> None:
        """The line is in the sweep exactly when the step is the dispatch."""
        for name, (files, runs, dispatch, step) in SWEEPS.items():
            out, line = said(APPROVED_PLAN, files, *runs, dispatch=dispatch)
            assert_that(LINE in out, equal_to(LINE in step), name)
            assert_that(line, contains_string(step), name)

    def test_a_dispatch_of_another_workflow_does_not_end_the_step(self) -> None:
        """Only a completed dispatch of check.yml counts, not any workflow's."""
        here = served(world_with(APPROVED_PLAN, draft=True), "files", [E2E_FILE])
        quietworld.unheld(here)
        served(here, "runs", {"check_runs": [RAN]})
        served(here, "dispatch", {"workflow_runs": []})
        served(here, "any", {"workflow_runs": list(DONE_RUN)})
        out = sweep(here).out
        assert_that(LINE in out, equal_to(True))

    def test_a_dispatch_of_check_yml_ends_the_step(self) -> None:
        """A completed dispatch of check.yml at the head ends it."""
        here = served(world_with(APPROVED_PLAN, draft=True), "files", [E2E_FILE])
        served(here, "runs", {"check_runs": [RAN]})
        served(here, "dispatch", {"workflow_runs": list(DONE_RUN)})
        out = sweep(here).out
        assert_that(LINE in out, equal_to(False))

    def test_the_line_replaces_the_wait_and_the_review(self) -> None:
        """No WAIT-FOR-CI line, and no review of the PR is listed."""
        out, _ = said(APPROVED_PLAN, [E2E_FILE])
        assert_that("WAIT-FOR-CI owner/project#3" in out, equal_to(False))

    def test_a_plan_that_is_not_approved_is_reviewed_first(self) -> None:
        """The Plan review comes before any e2e run."""
        out, line = said([], [E2E_FILE])
        assert_that("RUN E2E" in out + line, equal_to(False))


def step_of(
    review: shapes.Graded,
    touches: bool,
    *checks: shapes.CheckRun,
    dispatched: bool = False,
) -> object:
    """The step of a draft that has the review.

    Args:
        review: the review at its head.
        touches: whether its diff touches the e2e suite.
        *checks: the check runs of its head.
        dispatched: whether a dispatched run of its head has completed.

    Returns:
        The step.
    """
    found = state(review, checks=checks, draft=True, undraft_clear=True)
    wanted = dataclasses.replace(
        found.draft, needs_e2e=lambda: touches and not dispatched
    )
    return flow.next_step(dataclasses.replace(found, draft=wanted))


class TestTheFlow(unittest.TestCase):
    """The step, by what the caller read of the diff."""

    def test_each_case_has_its_step(self) -> None:
        """A draft whose Plan is approved, by its diff and its check runs."""
        branch = state(APPROVED_REVIEW).pull.head.branch
        found = [
            step_of(APPROVED_REVIEW, True),
            step_of(APPROVED_REVIEW, False),
            step_of(APPROVED_REVIEW, True, test_flow.GREEN, dispatched=True),
            step_of(REJECTED_REVIEW, True),
            step_of(APPROVED_REVIEW, True, test_flow.GREEN),
        ]
        ruling = steps.opus_ruling()
        wanted = [
            steps.run_e2e(branch),
            steps.undraft(),
            steps.undraft(),
            ruling,
            steps.run_e2e(branch),
        ]
        assert_that(found, equal_to(wanted))
        assert_that(steps.describe(wanted[0]), contains_string(f"on {branch}"))


class TestTheBrief(unittest.TestCase):
    """A review of such a PR reads the dispatched run."""

    def test_a_review_of_a_changed_e2e_says_not_started_without_a_run(self) -> None:
        """The sentence, in the kinds that read the head's checks."""
        head = make(brief.Kind.REVIEW_FULL).heads.head
        said_it = [built(kind, True) for kind in brief.E2E_KINDS]
        assert_that(len(said_it), equal_to(4))
        for found in said_it:
            assert_that(found, contains_string("dispatched on its branch"))
            assert_that(found, contains_string(f"`{NOT_STARTED} {head}`"))

    def test_a_review_of_another_pr_does_not_say_it(self) -> None:
        """No e2e change, no sentence; and a Plan review reads no run."""
        every = [built(kind, False) for kind in brief.REVIEWS]
        every.append(built(brief.Kind.REVIEW_PLAN, True))
        assert_that(any(NOT_STARTED in each for each in every), equal_to(False))

    def test_the_suggestion_of_a_review_says_it_for_a_changed_e2e(self) -> None:
        """A ready PR 3 that changes ``e2e/`` is reviewed with the sentence."""
        changed = served(world_with([]), "files", [E2E_FILE])
        assert_that(next_output(changed), contains_string(NOT_STARTED))
        assert_that(NOT_STARTED in next_output(world_with([])), equal_to(False))


class TestThePieces(unittest.TestCase):
    """The marker, the default prefix and the parser."""

    def test_the_marker_spells_the_step(self) -> None:
        """One text for the marker and the step."""
        found = markers.Marker.RUN_E2E_BEFORE_APPROVAL.text
        assert_that(found, equal_to(steps.RUN_E2E_MARKER))

    def test_the_parser_gives_the_ids_of_the_dispatched_runs(self) -> None:
        """The ids of a page of runs."""
        text = '{"workflow_runs": [{"id": 5}, {"id": 6}]}'
        assert_that(dispatchruns.run_ids(text), equal_to([5, 6]))

    def test_the_parser_gives_the_names_of_a_page(self) -> None:
        """A rename gives both."""
        text = '[{"filename": "a"}, {"filename": "b", "previous_filename": "c"}]'
        assert_that(pullfiles.file_names(text), equal_to(["a", "b", "c"]))


def held_e2e() -> world.World:
    """A world whose draft PR 3 needs the check workflow dispatched, a job waiting.

    Returns:
        The world.
    """
    here = served(world_with(APPROVED_PLAN, draft=True), "files", [E2E_FILE])
    return served(
        served(here, "runs", {"check_runs": []}), "dispatch", {"workflow_runs": []}
    )


class TestB20Dispatch(unittest.TestCase):
    """The hold withholds the dispatch (B20)."""

    def test_b20_a_dispatch_is_withheld_during_a_hold(self) -> None:
        """The check workflow is not dispatched during a hold; a control."""
        held = held_e2e()
        clear = quietworld.unheld(held_e2e())
        shown = [LINE in sweep(each).out for each in (held, clear)]
        assert_that(shown, equal_to([False, True]))
        assert_that(state_line(held), contains_string(HELD_WORDS))
