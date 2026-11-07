"""A draft's Plan review waits for the check its lint requires (pitboss#275).

The cause: quire's lint refuses an approving review of a head with no completed
green ``check`` run, draft or not, and a draft runs that job; the sweep offered
the review of a draft's Plan at once, the reviewer approved before the job
finished, and the lint stayed red until the head moved (quire#1058).
"""

import dataclasses
import pathlib
import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, draftfacts, shapes, steps
from . import fakes, test_flow, world
from .briefmake import has_none, make, text
from .test_commands import sweep
from .test_flow import state
from .test_flow_sweep import CHANGES, HEAD, OLDER, graded, world_with
from .test_slot_commands import next_output

CHECK_RUNS = f"{world.PROJECT}/commits/{HEAD}/check-runs"
WAITING = "next step: waiting for CI at this head"
REVIEW_LINE = "DRAFT ROUND owner/project#3: review it"
NOT_STARTED = "NOT STARTED: check is <state>"
SETTING = '\n[sweep]\nplan_review_check = "check"\n'


def run(name: str, status: str, conclusion: str | None) -> Mapping[str, object]:
    """A check run of the head, as GitHub gives it.

    Args:
        name: its name.
        status: ``queued``, ``in_progress`` or ``completed``.
        conclusion: how it ended, None while it has not.

    Returns:
        The run.
    """
    return {"id": 9, "name": name, "status": status, "conclusion": conclusion}


IN_PROGRESS = run("check", "in_progress", None)
QUEUED = run("check", "queued", None)
COMPLETED = run("check", "completed", "success")
CALLED = run("pr / check", "completed", "success")
OTHER = run("build", "completed", "success")
WAITS = {
    "a check run in progress": [IN_PROGRESS],
    "a check run queued": [QUEUED],
    "no check run at all": [],
    "only another check run, completed": [OTHER],
    "the check run in progress beside another": [OTHER, IN_PROGRESS],
}
GOES = {
    "the check run completed": [COMPLETED],
    "the check run completed beside another": [OTHER, COMPLETED],
    "the check job of a called workflow completed": [CALLED],
}


def draft(
    runs: Sequence[Mapping[str, object]],
    rounds: Sequence[shapes.Comment] = (),
    setting: str = SETTING,
) -> world.World:
    """A world whose draft PR 3 has the check runs, in a configured project.

    Args:
        runs: the check runs of its head.
        rounds: its comments.
        setting: the text appended to the configuration.

    Returns:
        The world.
    """
    here = world_with(rounds, draft=True)
    here.bodies.update({fakes.page(CHECK_RUNS): {"check_runs": list(runs)}})
    with pathlib.Path(here.config).open("a") as out:
        out.write(setting)
    return here


def offered(here: world.World) -> bool:
    """Whether ``slots next`` lists PR 3 for a review.

    Args:
        here: the world.

    Returns:
        True when a NEXT line is its review.
    """
    line = re.compile(r"^NEXT \d+\. owner/project#3 \(review it", re.MULTILINE)
    return bool(line.search(next_output(here)))


def state_line(here: world.World) -> str:
    """PR 3's PR STATE line.

    Args:
        here: the world.

    Returns:
        The line.
    """
    lines = next_output(here).splitlines()
    return "".join(each for each in lines if "PR STATE owner/project#3" in each)


class TestTheSweep(unittest.TestCase):
    """The sweep and ``slots next`` offer the review once the check completed."""

    def test_the_review_waits_for_the_check_run(self) -> None:
        """Waiting for CI, no review suggestion and no round line."""
        for name, runs in WAITS.items():
            here = draft(runs)
            assert_that(state_line(here), contains_string(WAITING), name)
            assert_that(offered(here), equal_to(False), name)
            assert_that(REVIEW_LINE in sweep(here).out, equal_to(False), name)

    def test_the_review_is_offered_when_the_check_run_completed(self) -> None:
        """The review suggestion, first in the list, and the round line."""
        for name, runs in GOES.items():
            here = draft(runs)
            assert_that(state_line(here), contains_string("next step: review"), name)
            assert_that(offered(here), equal_to(True), name)
            assert_that(REVIEW_LINE in sweep(here).out, equal_to(True), name)

    def test_a_revised_plan_waits_too(self) -> None:
        """The case of quire#1058: the head moved by an empty Plan commit."""
        rounds = [graded(CHANGES, None, 1, sha=OLDER)]
        waiting = draft([IN_PROGRESS], rounds)
        assert_that(state_line(waiting), contains_string(WAITING))
        done = draft([COMPLETED], rounds)
        assert_that(offered(done), equal_to(True))

    def test_a_project_with_no_setting_offers_it_at_once(self) -> None:
        """A draft has no check run to wait for, as before."""
        here = draft([IN_PROGRESS], setting="")
        assert_that(offered(here), equal_to(True))

    def test_the_suggestion_carries_the_sentence(self) -> None:
        """The brief ``slots next`` prints for the review reads the check run."""
        out = next_output(draft([COMPLETED]))
        assert_that(out, contains_string(NOT_STARTED))
        has_none(out, ["a draft has no check run, so there is no CI"])


class TestTheFlow(unittest.TestCase):
    """The step, by the check runs the caller read."""

    def test_each_case_has_its_step(self) -> None:
        """A draft with no review, by its check runs."""
        review = steps.regular_review(steps.Stage.PLAN_ONLY)
        cases: Sequence[tuple[Sequence[shapes.CheckRun], str, steps.Next]] = (
            ([], "build", steps.wait_for_ci()),
            ([test_flow.RUNNING], "lint", steps.wait_for_ci()),
            ([test_flow.GREEN], "lint", steps.wait_for_ci()),
            ([test_flow.GREEN], "build", review),
            ([test_flow.RED], "test", review),
        )
        for runs, name, wanted in cases:
            found = state(checks=runs, draft=True)
            draft = dataclasses.replace(found.draft, plan_review_check=name)
            test_flow.expect(wanted, dataclasses.replace(found, draft=draft))

    def test_no_setting_is_no_wait(self) -> None:
        """Without a check named, the review is due whatever runs."""
        found = state(checks=[test_flow.RUNNING], draft=True)
        test_flow.expect(steps.regular_review(steps.Stage.PLAN_ONLY), found)

    def test_a_red_completed_run_is_completed(self) -> None:
        """The run finished; whether it is green is the review's to read."""
        assert_that(draftfacts.completed([test_flow.RED], "test"), equal_to(True))

    def test_a_name_that_only_ends_alike_is_another_check(self) -> None:
        """Only ``caller / name`` matches, not any name that ends in it."""
        other = shapes.CheckRun(id=4, name="precheck", finished=True, failed=False)
        assert_that(draftfacts.completed([other], "check"), equal_to(False))


class TestTheConfiguration(unittest.TestCase):
    """``[sweep] plan_review_check`` names the check."""

    def test_the_key_is_read_and_defaults_to_none(self) -> None:
        """Empty when the table says nothing."""
        directory = fakes.directory()
        for extra, wanted in (("", ""), (SETTING, "check")):
            settings = fakes.settings(directory, extra)
            assert_that(settings.project.plan_review_check, equal_to(wanted))


class TestTheBrief(unittest.TestCase):
    """The Plan review of a draft reads the check run when the project has one."""

    def test_the_brief_says_to_read_the_check_run(self) -> None:
        """The NOT STARTED sentence, and not the sentence that a draft has none."""
        found = text(brief.Kind.REVIEW_PLAN, plan_check="check")
        assert_that(found, contains_string(NOT_STARTED))
        assert_that(found, contains_string("`check` check run of the head SHA"))
        has_none(found, ["a draft has no check run", "never hand back `NOT STARTED`"])

    def test_a_ready_pr_keeps_the_ci_sentence(self) -> None:
        """Only a draft's brief changes."""
        spec = dataclasses.replace(
            make(brief.Kind.REVIEW_PLAN, plan_check="check"), ready=True
        )
        has_none(brief.build(spec), [NOT_STARTED])
