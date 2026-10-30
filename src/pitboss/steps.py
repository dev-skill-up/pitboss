"""The steps of the review flow of a PR (keyword: review-flow).

A step says what happens next to a PR: who acts and on what. ``flow.next_step``
gives one; ``describe`` says it in a line.
"""

import dataclasses
import enum
from typing import Mapping

PAUSED_LABEL = "paused-owner"
RULING_FIRST_LINE = "Opus ruling"
FIRST_STEP = (
    "write the code, open the PR as a draft whose body has a Plan section and an"
    " Execution section; no open PR says it fixes this ticket"
)


class Step(enum.Enum):
    """What happens next to a PR.

    Attributes:
        WAIT_FOR_OWNER: the PR is paused; the owner decides.
        WORKER: a worker does a task.
        UNDRAFT: mark the PR ready.
        REGULAR_REVIEW: a new reviewer grades a stage.
        WAIT_FOR_UNDRAFT: the plan is approved, the PR cannot be undrafted yet.
        WAIT_FOR_CI: CI on the head has not finished; nobody works meanwhile.
        OPUS_RULING: one Opus agent makes a binding ruling.
        PAUSE_FOR_OWNER: pause the PR and tell the owner the options.
        MERGE: the PR merges.
    """

    WAIT_FOR_OWNER = enum.auto()
    WORKER = enum.auto()
    UNDRAFT = enum.auto()
    REGULAR_REVIEW = enum.auto()
    WAIT_FOR_UNDRAFT = enum.auto()
    WAIT_FOR_CI = enum.auto()
    OPUS_RULING = enum.auto()
    PAUSE_FOR_OWNER = enum.auto()
    MERGE = enum.auto()


class Task(enum.Enum):
    """What a worker is told to do; the value is the text.

    Attributes:
        FIRST_ROUND: the first work on a PR with no Plan and Execution body.
        FIX_CI: the head's CI is red.
        REVISE_PLAN: the plan alone, no code.
        RESOLVE_CONFLICT: the approved head conflicts with the base.
        FIX_EXECUTION: the execution, against the approved plan.
        RULING_STEPS: exactly the steps of an Opus ruling.
        RULING_AS_GIVEN: what an Opus ruling says to the ticket and the PR.
    """

    FIRST_ROUND = "fix as best it can and write Plan and Execution in the body"
    FIX_CI = "fix CI on the head (a red CI is never a rejection)"
    REVISE_PLAN = "revise the PLAN only, change no code"
    RESOLVE_CONFLICT = "resolve the conflict"
    FIX_EXECUTION = "fix the execution against the approved plan"
    RULING_STEPS = "do exactly the steps of the Opus ruling"
    RULING_AS_GIVEN = (
        "do exactly what the Opus ruling says to the ticket and the PR (split,"
        " reshape or abandon); it is not checked against the one-ticket-one-PR"
        " rules"
    )


class Stage(enum.Enum):
    """What a reviewer is told to grade; the value is the text.

    Attributes:
        PLAN_ONLY: the Plan, with no Execution line.
        EXECUTION_ONLY: the Execution; the Plan is carried over as approved.
        PLAN_AND_EXECUTION: both, in one review.
        EXECUTION_AGAINST_PLAN: the Execution against the approved Plan.
        RULING_STEPS: only the steps of an Opus ruling.
    """

    PLAN_ONLY = (
        "grade the Plan ONLY (no Execution line); changes needed is a Plan rejection"
    )
    EXECUTION_ONLY = "review ONLY the Execution; the Plan is carried over as approved"
    PLAN_AND_EXECUTION = "grade Plan and Execution together"
    EXECUTION_AGAINST_PLAN = "grade the Execution against the approved Plan"
    RULING_STEPS = "review ONLY the steps of the Opus ruling and nothing new"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Next:
    """One step.

    Attributes:
        step: what happens.
        task: what the worker does (a WORKER step).
        stage: what the reviewer grades (a REGULAR_REVIEW step).
    """

    step: Step
    task: Task | None = None
    stage: Stage | None = None


TEXTS: Mapping[Step, str] = {
    Step.WAIT_FOR_OWNER: (
        f"the PR is paused (label {PAUSED_LABEL}); nobody works on it until the"
        " owner decides"
    ),
    Step.UNDRAFT: (
        "mark the PR ready; the next step is the CI gate on the undrafted head"
    ),
    Step.WAIT_FOR_UNDRAFT: (
        "the plan is approved but the PR cannot be undrafted yet (runner pressure"
        " or the quiet period); wait for the window"
    ),
    Step.WAIT_FOR_CI: (
        "CI on the current head has not finished; nobody works or reviews" " meanwhile"
    ),
    Step.OPUS_RULING: (
        "start an Opus agent whose only brief is to make a ruling, and record it"
        f" as a PR comment whose first line is {RULING_FIRST_LINE!r}"
    ),
    Step.PAUSE_FOR_OWNER: (
        f"label the PR and its ticket {PAUSED_LABEL}, comment what the rounds"
        " disagreed about and the options, and report the number and the options"
        " to the owner"
    ),
    Step.MERGE: "CI is green and there is no conflict: arm auto-merge or merge",
}


def describe(step: Next) -> str:
    """Say what to do for a step, in one line.

    Args:
        step: the step.

    Returns:
        Its task, its stage, or the text of the step.
    """
    if step.task is not None:
        return step.task.value
    if step.stage is not None:
        return step.stage.value
    return TEXTS[step.step]


def wait_for_owner() -> Next:
    """The step of a PR paused for the owner.

    Returns:
        The step.
    """
    return Next(step=Step.WAIT_FOR_OWNER)


def worker(task: Task) -> Next:
    """A worker round.

    Args:
        task: what the worker does.

    Returns:
        The step.
    """
    return Next(step=Step.WORKER, task=task)


def undraft() -> Next:
    """The step that marks a draft ready.

    Returns:
        The step.
    """
    return Next(step=Step.UNDRAFT)


def regular_review(stage: Stage) -> Next:
    """A review by a new reviewer.

    Args:
        stage: what it grades.

    Returns:
        The step.
    """
    return Next(step=Step.REGULAR_REVIEW, stage=stage)


def wait_for_undraft() -> Next:
    """The step of a draft with an approved plan that cannot be undrafted yet.

    Returns:
        The step.
    """
    return Next(step=Step.WAIT_FOR_UNDRAFT)


def wait_for_ci() -> Next:
    """The step of a head whose CI has not finished.

    Returns:
        The step.
    """
    return Next(step=Step.WAIT_FOR_CI)


def opus_ruling() -> Next:
    """The step that asks Opus for a ruling.

    Returns:
        The step.
    """
    return Next(step=Step.OPUS_RULING)


def pause_for_owner() -> Next:
    """The step that pauses the PR for the owner.

    Returns:
        The step.
    """
    return Next(step=Step.PAUSE_FOR_OWNER)


def merge() -> Next:
    """The step that merges.

    Returns:
        The step.
    """
    return Next(step=Step.MERGE)
