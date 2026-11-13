"""A PR handed back unfinished is finished, in order (keyword: finish-partial).

quire#1119 was handed back partial and fell out of the order: its Plan check was
never posted, its body failed the lint, and ``slots next`` offered it to nobody.
Each shape below is played with a fake GitHub and the slot ledger.
"""

import dataclasses
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import finishpartial, pulls, shapes, steps, work
from . import fakes, quietworld, world
from .test_commands import sweep
from .test_slot_commands import next_output
from .test_work import NONE, facts, item

PROJECT = world.PROJECT
COMMANDS = "Fixes #7\n\n## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n"
NOT_CHECKED = "no clean Plan check covers the Plan"
STATE = "PR STATE owner/project#3: next step: finish the PR a worker handed back"
PARTIAL = "FINISH PARTIAL owner/project#3:"
FINISH = work.Category.FINISH_PARTIAL
RED = shapes.CommitStatus(
    context="text-lint",
    succeeded=False,
    created_at="2026-10-01T10:00:00Z",
    run=0,
    state="failure",
    description="no Head line",
    url="",
)


def partial_world(body: str = COMMANDS) -> world.World:
    """A world whose PR 3 has a Plan with commands and no Plan check.

    Args:
        body: PR 3's body.

    Returns:
        The world.
    """
    here = world.make_world()
    head = {"sha": "3" * 40, "ref": "branch-3"}
    changed = fakes.pull_body(3, head=head, mergeable_state="behind", body=body)
    here.bodies[f"{PROJECT}/pulls/3"] = changed
    return quietworld.unheld(here)


def hold_pr_3(here: world.World) -> None:
    """Make the ledger hold PR 3 in its first slot.

    Args:
        here: the world.
    """
    slot = {
        "name": "tiny",
        "model": "small",
        "agent": "worker-1",
        "task": "owner/project#3",
        "started": "2030-01-01T00:00:00Z",
    }
    other = {"name": "big", "model": "large"}
    here.ledger.write_text(json.dumps({"slots": [slot, other], "failed": {}}))


def lines_of(here: world.World, word: str) -> Sequence[str]:
    """The lines of ``slots next`` that hold a word.

    Args:
        here: the world.
        word: the word.

    Returns:
        The lines.
    """
    return [each for each in next_output(here).splitlines() if word in each]


def at_step(step: steps.Move, *statuses: shapes.CommitStatus) -> pulls.PullFacts:
    """An open PR at a step with failed statuses.

    Args:
        step: its step.
        *statuses: the failed commit statuses of its head.

    Returns:
        The PR.
    """
    pull = facts(3, NONE)
    signals = dataclasses.replace(pull.signals, statuses=statuses)
    return dataclasses.replace(pull, step=step, signals=signals)


class TestOffered(unittest.TestCase):
    """The sweep and ``slots next`` offer the PR to a free slot."""

    def test_c24_a_draft_with_no_plan_check_and_no_worker_is_offered(self) -> None:
        """The step is the finishing, its line names the missing check."""
        here = partial_world()
        text = next_output(here)
        assert_that(text, contains_string(STATE))
        assert_that(text, contains_string("NEXT 3. owner/project#3 (finish the PR"))
        assert_that(text, contains_string(NOT_CHECKED))

    def test_c24_the_sweep_names_the_pr_and_what_is_missing(self) -> None:
        """The FINISH PARTIAL line is in the sweep."""
        out = sweep(partial_world()).out
        assert_that(out, contains_string(PARTIAL))

    def test_c24_a_pr_a_slot_holds_is_not_offered_again(self) -> None:
        """The ledger holds PR 3: it is the worker's, not offered to a second."""
        here = partial_world()
        hold_pr_3(here)
        assert_that(lines_of(here, "start owner/project#3"), equal_to([]))
        assert_that(lines_of(here, "NEXT 3. owner/project#3"), equal_to([]))

    def test_c24_a_slot_released_with_work_unfinished_offers_it(self) -> None:
        """The ledger has no holder: the free slot starts the PR."""
        here = partial_world()
        text = lines_of(here, "EMPTY SLOT")
        assert_that(text[0], contains_string("start owner/project#3 (finish the PR"))

    def test_c24_a_ready_pr_with_a_clean_check_is_not_partial(self) -> None:
        """The default PR 3 (reviewable, no commands) keeps the review step."""
        text = next_output(quietworld.unheld(world.make_world()))
        assert_that(
            text, contains_string("PR STATE owner/project#3: next step: review")
        )
        assert_that(text.count(PARTIAL), equal_to(0))


def settled(
    step: steps.Move, *statuses: shapes.CommitStatus
) -> tuple[pulls.PullFacts, Sequence[str]]:
    """The one PR at a step after ``settle``.

    Args:
        step: its step.
        *statuses: the failed commit statuses of its head.

    Returns:
        The PR and the sweep's lines.
    """
    read, lines = finishpartial.settle([at_step(step, *statuses)])
    return pulls.readable(read)[0], lines


SEND_BACK = dataclasses.replace(
    steps.plan_check(),
    step=steps.Step.SEND_BACK_PLAN_CHECK,
    findings="row 1: NOT RUN",
)
GATED = (
    steps.regular_review(steps.Stage.PLAN_AND_EXECUTION),
    steps.undraft(),
    steps.ci_pending(),
    steps.merge(),
)
KEPT = (
    at_step(steps.worker(steps.Task.FIX_CI), RED),
    at_step(steps.OWNER_PENDING, RED),
    at_step(steps.merge()),
    shapes.Unreadable(reference="owner/project#8", call="x", status="500"),
)


class TestShapes(unittest.TestCase):
    """The states, one by one, with the PR facts."""

    def test_c24_a_pr_with_no_clean_plan_check_becomes_the_finishing_step(self) -> None:
        """PLAN_CHECK is offered to nobody; it becomes the finishing step."""
        pull, lines = settled(steps.plan_check())
        assert_that(work.category_of(pull), equal_to(work.Category.FINISH_PARTIAL))
        assert_that(lines[0], contains_string(NOT_CHECKED))

    def test_c24_a_refused_check_stays_the_pushing_workers_and_is_named(self) -> None:
        """Pitboss#471: no round is offered for it; the sweep says NO STEP."""
        pull, lines = settled(SEND_BACK)
        assert_that(steps.step_of(pull.step), equal_to(steps.Step.SEND_BACK_PLAN_CHECK))
        assert_that(lines, equal_to([]))

    def test_c24_a_red_text_lint_on_a_pr_to_review_or_merge_is_partial(self) -> None:
        """A body that fails `lint pr-body` is finished, not reviewed or merged."""
        done = [settled(each, RED) for each in GATED]
        assert_that(
            [steps.task_of(pull.step) for pull, _ in done],
            equal_to([steps.Task.FINISH_PARTIAL] * len(GATED)),
        )
        assert_that(
            all("no Head line" in lines[0] for _, lines in done), equal_to(True)
        )

    def test_c24_other_pulls_are_left_as_they_are(self) -> None:
        """A worker's fix, a wait, a green PR and an unreadable PR keep their step."""
        read, lines = finishpartial.settle(KEPT)
        assert_that([list(read), list(lines)], equal_to([list(KEPT), []]))

    def test_c24_a_status_that_is_not_text_lint_or_not_red_is_no_reason(self) -> None:
        """Another context, or a pending text-lint, does not make a PR partial."""
        other = dataclasses.replace(RED, context="canonical-files")
        pending = dataclasses.replace(RED, state="pending")
        pull = settled(steps.merge(), other, pending)[0]
        assert_that(steps.step_of(pull.step), equal_to(steps.Step.MERGE))


class TestStranded(unittest.TestCase):
    """The sweep names a PR that has no step."""

    def test_c24_a_pr_offered_for_nothing_is_named(self) -> None:
        """A refused check no worker sends back, or a check step left unsettled."""
        left = [at_step(SEND_BACK), at_step(steps.plan_check())]
        found = finishpartial.stranded(left)
        assert_that(len(found), equal_to(2))
        assert_that(found[0], contains_string("NO STEP owner/project#3"))

    def test_c24_a_settled_pr_is_not_named(self) -> None:
        """After `settle` the check step is the finishing step: it has a step."""
        settled_pr = finishpartial.settle([at_step(steps.plan_check())])[0]
        assert_that(list(finishpartial.stranded(settled_pr)), equal_to([]))


class TestOrder(unittest.TestCase):
    """It is a PR that needs work: oldest first, ahead of the new tickets."""

    def test_c24_it_comes_before_a_new_ticket_and_by_age(self) -> None:
        """Two finishing items, oldest first, then the ticket."""
        kinds = {9: work.Category.NEW_PR, 5: FINISH, 4: FINISH}
        made = [item(f"owner/project#{each}", kind) for each, kind in kinds.items()]
        young = dataclasses.replace(made[1], created_at="2027")
        ordered = work.ordered([made[0], young, made[2]], [])
        assert_that([each.reference[-1] for each in ordered], equal_to(["4", "5", "9"]))

    def test_c24_the_brief_resumes_the_same_pr(self) -> None:
        """The brief tells the worker to resume the PR, not start a new one."""
        out = next_output(partial_world())
        assert_that(out, contains_string("Resume this PR on its own branch"))
        assert_that(out, contains_string("PITBOSS-SLOT: owner/project#3 fix"))


_ = fakes
