"""Tests for a red CI the base has passed since (keyword: fixed-on-base, pitboss#314).

In a repository with a merge queue the sweep never offers an update or a merge of
the base into a PR but for a conflict, and a PR red only from checks that passed
on the base since is enqueued when approved and reviewed when not.
"""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import basefix, fixedline, flow, headchecks, reviews, shapes, steps
from . import fakes, syncworld, test_commands, test_flow, test_work, world
from .test_commands import sweep
from .test_slot_commands import next_output

QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
PROJECT = world.PROJECT
# before the review of PR 2 (world.COMMENT, 2026-10-02): a review that precedes
# the head's completed checks does not count
FAILED_AT = "2026-10-01T10:00:00Z"
PASSED_AT = "2026-10-01T12:00:00Z"
RED_RUN = {
    "id": 8,
    "name": "test",
    "status": "completed",
    "conclusion": "failure",
    "started_at": "2026-10-01T09:50:00Z",
    "completed_at": FAILED_AT,
}
GREEN_RUN = dict(RED_RUN, conclusion="success")
BASE_PASSED = {
    "id": 99,
    "name": "test",
    "status": "completed",
    "conclusion": "success",
    "head_sha": "9" * 40,
    "started_at": "2026-10-01T11:50:00Z",
    "completed_at": PASSED_AT,
}
BASE_FAILED = dict(BASE_PASSED, conclusion="failure")
BASE_CANCELLED = dict(BASE_PASSED, conclusion="cancelled")
BASE_BEFORE = dict(BASE_PASSED, completed_at="2026-10-01T09:00:00Z")
BASE_NEWER_FAILED = dict(
    BASE_FAILED,
    id=100,
    started_at="2026-10-01T12:50:00Z",
    completed_at="2026-10-01T13:00:00Z",
)
BASE_OTHER = dict(BASE_PASSED, name="lint")
ENQUEUE = "enqueue it (the merge queue tests it on main)"
REQUEST = "request the review"
FIXED = (
    "FIXED ON BASE owner/project#{n}: test (job 8) failed at 2026-10-01T10:00:00Z,"
    " passed on the base at 2026-10-01T12:00:00Z (job 99); the red CI is no work"
    " and main is not merged into branch-{n}: {action}"
)
FIXED_3 = FIXED.format(n=3, action=REQUEST)
FIXED_2 = FIXED.format(n=2, action=ENQUEUE)
FAILED_3 = "FAILED owner/project#3: test"
CONFLICT_3 = "CONFLICT owner/project#3: merge main into branch-3"
REVIEW_3 = "owner/project#3 (review it"
STATE_3 = "PR STATE owner/project#3: next step: "
FIX_CI_3 = "owner/project#3 (fix the CI"
RED = dataclasses.replace(test_flow.RED, completed_at=FAILED_AT)
PASSED = shapes.CheckRun(
    id=99, name="test", finished=True, failed=False, succeeded=True, head_sha="9" * 40
)
ANSWER = basefix.Answer(failed=RED, passed=PASSED)


def red_world(
    pr: tuple[int, str],
    base: Sequence[object],
    extra: str = QUEUE,
    checks: Sequence[object] = (RED_RUN,),
) -> world.World:
    """A world whose PR has check runs, with the base's runs.

    Args:
        pr: its number (2 is approved at its head, 3 has no review) and its
            ``mergeable_state``.
        base: the check runs of the base branch's tip.
        extra: more TOML appended to the configuration.
        checks: the check runs of its head.

    Returns:
        The world.
    """
    here = world.make_world()
    add_pull(here, pr, base, checks)
    fakes.settings(here.workspace, (world.EXTRA + extra).format(ledger=here.ledger))
    return here


def add_pull(
    here: world.World,
    pr: tuple[int, str],
    base: Sequence[object],
    checks: Sequence[object],
) -> None:
    """Put a PR with check runs, and the base's runs, in a world.

    Args:
        here: the world.
        pr: the PR's number and ``mergeable_state``.
        base: the check runs of the base branch's tip.
        checks: the check runs of the PR's head.
    """
    number, state = pr
    head = fakes.HEAD if number == 2 else str(number) * 40
    ref = {"sha": head, "ref": f"branch-{number}"}
    here.bodies[f"{PROJECT}/pulls/{number}"] = fakes.pull_body(
        number, head=ref, mergeable_state=state
    )
    for commit, runs in ((head, checks), ("main", base)):
        path = fakes.page(f"{PROJECT}/commits/{commit}/check-runs")
        here.bodies[path] = {"check_runs": list(runs)}


# each: what the world is, the sweep lines that start with a text (or not), the
# words ``slots next`` has (or not), and whether the base's check runs were read
Case = tuple[str, dict[str, object], Mapping[str, bool], Mapping[str, bool], bool]


def unpassed(label: str, base: Sequence[object]) -> Case:
    """A case: the base has not passed the failed check since.

    Args:
        label: why not.
        base: the check runs of the base branch's tip.

    Returns:
        The case: the PR is still red, and told to fix the CI.
    """
    return (
        f"red, the base has not passed it since ({label})",
        {"pr": (3, "behind"), "base": base},
        {FAILED_3: True, "FIXED ON BASE": False},
        {FIX_CI_3: True},
        True,
    )


CASES: Sequence[Case] = [
    (
        "behind, red, fixed on the base, no review",
        dict(pr=(3, "behind"), base=[BASE_PASSED]),
        {FIXED_3: True, FAILED_3: False, "UPDATE": False, CONFLICT_3: False},
        {REVIEW_3: True, FIX_CI_3: False, STATE_3 + REQUEST: True},
        True,
    ),
    (
        "clean, red, fixed on the base, approved",
        dict(pr=(2, "clean"), base=[BASE_PASSED]),
        {FIXED_2: True, "FAILED owner/project#2": False, "READY TO MERGE": False},
        {STATE_3.replace("#3", "#2") + ENQUEUE: True},
        True,
    ),
    (
        "behind and conflicting, red, fixed on the base",
        dict(pr=(3, "dirty"), base=[BASE_PASSED]),
        {CONFLICT_3: True, "FIXED ON BASE owner/project#3": False},
        {"owner/project#3 (resolve the conflict": True, FIX_CI_3: False},
        True,
    ),
    (
        "behind but mergeable, green",
        dict(pr=(3, "behind"), base=[], checks=[GREEN_RUN]),
        {"UPDATE": False, "FIXED ON BASE": False, "FAILED owner/project#3": False},
        {REVIEW_3: True, "(update": False},
        True,  # PR 1 of the world is red
    ),
    (
        "red, fixed on the base, in a repository with no merge queue",
        dict(pr=(3, "behind"), base=[BASE_PASSED], extra=""),
        {FAILED_3: True, "FIXED ON BASE": False},
        {FIX_CI_3: True},
        False,
    ),
    *[
        unpassed(label, base)
        for label, base in [
            ("failed", [BASE_FAILED]),
            ("cancelled", [BASE_CANCELLED]),
            ("before", [BASE_BEFORE]),
            ("another check", [BASE_OTHER]),
            ("no run", []),
            ("older pass, newer failure", [BASE_PASSED, BASE_NEWER_FAILED]),
            ("newer failure listed first", [BASE_NEWER_FAILED, BASE_PASSED]),
        ]
    ],
]


class TestSweep(unittest.TestCase):
    """``pitboss sweep`` and ``pitboss slots next`` of a merge-queue repository."""

    def test_a_pr_gets_the_line_its_state_calls_for(self) -> None:
        """Only a conflict is merged; a red CI the base passed is enqueued or not."""
        for label, build, said, listed, read in CASES:
            with self.subTest(label):
                here = red_world(**build)  # type: ignore[arg-type]
                out, text = sweep(here).out.splitlines(), next_output(here)
                found = (
                    {head: any(line.startswith(head) for line in out) for head in said},
                    {word: word in text for word in listed},
                    any("commits/main/check-runs" in " ".join(c) for c in here.calls),
                )
                assert_that(found, equal_to((said, listed, read)))


def exit_and_logs(base: Sequence[object]) -> tuple[int, bool]:
    """Sweep a world whose only open PR of the project is the red PR 3.

    Args:
        base: the check runs of the base branch's tip.

    Returns:
        The sweep's exit code, and whether it read the failed job's log.
    """
    here = syncworld.make_synced(QUEUE).here
    add_pull(here, (3, "behind"), base, (RED_RUN,))
    here.bodies.update({test_commands.OPEN_PULLS: [{"number": 3}]})
    code = int(str(sweep(here).code))
    logs = [call for call in here.calls if "actions/jobs/8" in " ".join(call)]
    return code, bool(logs)


class TestExit(unittest.TestCase):
    """The exit status of ``pitboss sweep`` and the failure logs it reads."""

    def test_only_an_unanswered_failed_check_makes_it_exit_one(self) -> None:
        """Answered: exit 0 and no log read; unanswered: exit 1 and the log read."""
        found = [exit_and_logs(base) for base in ([BASE_PASSED], [])]
        assert_that(found, equal_to([(0, False), (1, True)]))


class TestLine(unittest.TestCase):
    """``fixedline.lines`` alone."""

    def test_another_step_is_named_as_it_is(self) -> None:
        """A review that asked for changes: the fix of the review, no CI fix."""
        step = steps.worker(steps.Task.FIX_EXECUTION)
        pull = dataclasses.replace(
            test_work.facts(3, reviews.Standing.CHANGES_NEEDED),
            checks=(RED,),
            step=step,
            signals=headchecks.HeadSignals(fixed=[ANSWER]),
        )
        assert_that(
            fixedline.lines(pull)[0].endswith(f"next step: {steps.describe(step)}"),
            equal_to(True),
        )


class TestAnswers(unittest.TestCase):
    """``basefix.answers`` on parsed check runs."""

    def test_every_failed_check_needs_a_later_pass(self) -> None:
        """One answered check of two is not an answer."""
        other = dataclasses.replace(RED, id=3, name="lint")
        late = dataclasses.replace(PASSED, completed_at=PASSED_AT)
        unfinished = dataclasses.replace(RED, completed_at="")
        found = [
            len(basefix.answers(failed, [late]))
            for failed in ([RED], [RED, other], [], [unfinished])
        ]
        assert_that(found, equal_to([1, 0, 0, 0]))


def step_of(
    recorded: Sequence[shapes.Graded], found: Sequence[basefix.Answer], merge: str
) -> steps.Next:
    """The step of a PR whose head is red, as the flow reads its checks.

    Args:
        recorded: its reviews.
        found: the base's answers to the failed check.
        merge: its ``mergeable_state``.

    Returns:
        The step.
    """
    checks = basefix.settle((RED,), found)
    return flow.next_step(
        test_flow.state(*recorded, checks=checks, mergeable_state=merge)
    )


class TestFlow(unittest.TestCase):
    """``flow.next_step`` of a red head the base has passed."""

    def test_the_step_is_the_one_a_green_head_gets(self) -> None:
        """No review: the review; approved: the merge; a conflict: its resolution."""
        yes = test_flow.APPROVED
        approved = (test_flow.graded(yes, yes, 1),)
        both = steps.Stage.PLAN_AND_EXECUTION
        resolve = steps.worker(steps.Task.RESOLVE_CONFLICT)
        cases = [
            ((), [], "clean", steps.worker(steps.Task.FIX_CI)),
            ((), [ANSWER], "clean", steps.regular_review(both)),
            (approved, [ANSWER], "clean", steps.merge()),
            ((), [ANSWER], "dirty", resolve),
        ]
        found = [step_of(*case[:3]) for case in cases]
        assert_that(found, equal_to([case[3] for case in cases]))

    def test_the_words_of_the_steps(self) -> None:
        """An enqueue and a request for the review are said as the ticket says."""
        both = steps.Stage.PLAN_AND_EXECUTION
        merge, review = steps.merge(), steps.regular_review(both)
        said = [
            steps.describe(dataclasses.replace(merge, on_base=True)),
            steps.describe(dataclasses.replace(review, on_base=True)),
            steps.describe(merge).startswith(ENQUEUE),
        ]
        assert_that(said, equal_to([ENQUEUE, f"{REQUEST}: {both.value}", False]))
