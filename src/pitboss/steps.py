"""The steps of the review flow of a PR (keyword: review-flow).

A step says what happens next to a PR: who acts and on what. ``flow.next_step``
gives one; ``describe`` says it in a line.
"""

import dataclasses
import enum
from typing import AbstractSet

PAUSED_LABEL = "paused-owner"
RULING_FIRST_LINE = "Opus ruling"
PLAN_CHECK_FIRST_LINE = "Plan check"  # keyword: plan-check (pitboss#192)
PLAN_CHECK_OK = "Plan check: ok"
RUN_E2E_MARKER = "RUN E2E BEFORE APPROVAL"  # keyword: run-e2e (pitboss#199)
# keyword: owner-artifact (pitboss#237, the owner's standing ruling of 2026-11-04)
OWNER_ARTIFACT = (
    "attach a markdown artifact with the sections 'What happened', 'Recommendation' "
    "and 'Suggested mitigation'"
)
FIRST_STEP = (
    "write the code, open the PR as a draft whose body has a Plan section and an"
    " Execution section; no open PR says it fixes this ticket"
)
# keyword: no-drafts (pitboss#216): the step of a project whose config has no drafts
FIRST_STEP_READY = (
    "write the code, open the PR ready for review (this repository has no drafts)"
    " with a body that has a Plan section and an Execution section; no open PR"
    " says it fixes this ticket"
)


class Step(enum.Enum):
    """What happens next to a PR.

    Attributes:
        WORKER: a worker does a task.
        UNDRAFT: mark the PR ready (a draft approved at its head, pitboss#176).
        REGULAR_REVIEW: a new reviewer grades a stage.
        OPUS_RULING: one Opus agent makes a binding ruling.
        PAUSE_FOR_OWNER: pause the PR and tell the owner the options.
        FIX_RULING: the newest Opus ruling has no readable ``Ruling:`` line.
        RULING_ESCALATES: the Opus ruling escalated to the owner.
        PLAN_EDITED: the approved Plan was edited, no ruling allows it (plan-digest).
        PLAN_CHECK: no comment records a clean ``pitboss plan-check`` (plan-check).
        SEND_BACK_PLAN_CHECK: the Plan check refused the Plan: send it back (#471).
        RUN_E2E: dispatch ``check.yml`` at the head of a draft whose diff touches e2e.
        MERGE: the PR merges.
    """

    WORKER = enum.auto()
    UNDRAFT = enum.auto()
    REGULAR_REVIEW = enum.auto()
    OPUS_RULING = enum.auto()
    PAUSE_FOR_OWNER = enum.auto()
    FIX_RULING = enum.auto()
    RULING_ESCALATES = enum.auto()
    PLAN_EDITED = enum.auto()
    PLAN_CHECK = enum.auto()
    SEND_BACK_PLAN_CHECK = enum.auto()
    RUN_E2E = enum.auto()
    MERGE = enum.auto()


class Task(enum.Enum):
    """What a worker is told to do; the value is the text.

    Attributes:
        FIRST_ROUND: the first work on a PR with no Plan and Execution body.
        FIX_CI: the head's CI is red.
        REVISE_PLAN: the plan alone, no code.
        RESOLVE_CONFLICT: the head conflicts with the base.
        FIX_EXECUTION: the execution, against the approved plan.
        RULING_STEPS: exactly the steps of an Opus ruling.
        RULING_AS_GIVEN: what an Opus ruling says to the ticket and the PR.
        RUN_PLAN: run the commands of a Plan approved alone (plan-alone).
        ADD_CI_QUOTES: the body lacks the Plan's CI quotes (keyword: ci-quotes).
        FIX_ROUND: findings name a file of the tree (fix-round-kind).
        REFRESH_BODY: the body names an older head (keyword: stale-head, quire#1115).
        SHARED_RED: file ONE ticket for a check red on several PRs (shared-red).
        FIX_BLOCKED_BY: a Blocked-by line names a loop or a closed blocker.
        AFTER_BLOCKER: the blockers merged since the red check (keyword: blocked-by).
        FINISH_PARTIAL: a worker handed back a PR unfinished (keyword: finish-partial).
    """

    FIRST_ROUND = "fix as best it can and write Plan and Execution in the body"
    FIX_CI = "fix CI on the head (a red CI is never a rejection)"
    REVISE_PLAN = "revise the PLAN only, change no code"
    RESOLVE_CONFLICT = "resolve the conflict"
    FIX_EXECUTION = "fix the execution against the approved plan"
    RULING_STEPS = "do exactly the steps of the Opus ruling"
    RULING_AS_GIVEN = (
        "do exactly what the Opus ruling says to the ticket and the PR (split,"
        " reshape or abandon); it is not checked against the one-ticket-one-PR rules"
    )
    RUN_PLAN = "run the approved Plan's commands as written and fill the Execution"
    ADD_CI_QUOTES = "add the CI quotes to the body"
    FIX_ROUND = "fix round: fix the findings, each one (code, doc, test, Plan)"
    REFRESH_BODY = (
        "rewrite the body's Head line and stale Evidence for the head:"
        " `pitboss body-head`, `pitboss expand`; `pitboss lint pr-body` must print ok"
    )
    SHARED_RED = "file one ticket against the shared cause of the red check; fix no PR"
    FIX_BLOCKED_BY = "correct the Blocked-by lines (a loop, or a blocker closed)"
    AFTER_BLOCKER = "the blockers merged: merge the base into the branch, check, push"
    FINISH_PARTIAL = "finish this PR, handed back unfinished"


class Stage(enum.Enum):
    """What a reviewer is told to grade; the value is the text.

    Attributes:
        PLAN_ONLY: the Plan, with no Execution line.
        EXECUTION_ONLY: the Execution; the Plan is carried over as approved.
        PLAN_AND_EXECUTION: both, in one review.
        EXECUTION_AGAINST_PLAN: the Execution against the approved Plan.
        RULING_STEPS: only the steps of an Opus ruling.
    """

    PLAN_ONLY = "grade the Plan ONLY (no Execution line); changes needed rejects it"
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
        comment: the address of the Opus ruling comment that cannot be read (a
            FIX_RULING step), of the refused Plan check (SEND_BACK_PLAN_CHECK) or
            of the ruling a FIX_EXECUTION or RULING_STEPS step follows, else empty.
        findings: the refused Plan check's findings, quoted.
        branch: the head branch the check workflow is dispatched on (RUN_E2E).
        on_base: the head is red only from checks that passed on the base since
            (keyword: fixed-on-base, pitboss#314): the step is a green head's.
        reason: why the review of a ruling's steps follows (keyword: ruling-reason,
            case 24), empty for any other step.
        conflict: ``FIRST SECOND``, the pair of rules an Opus ruling is to settle
            (keyword: rule-conflicts), empty for any other step.
    """

    step: Step
    task: Task | None = None
    stage: Stage | None = None
    comment: str = ""
    findings: str = ""
    branch: str = ""
    on_base: bool = False
    reason: str = ""
    conflict: str = ""


# the steps at which a ruling or the owner is owed (pitboss#148) or an edited
# approved Plan is to be restored (pitboss#172): no conflict is resolved meanwhile
UNRESOLVED = frozenset(
    {
        Step.OPUS_RULING,
        Step.PAUSE_FOR_OWNER,
        Step.RULING_ESCALATES,
        Step.PLAN_EDITED,
    }
)
HELD = frozenset({Step.MERGE, Step.RUN_E2E})  # keyword: hold-scope, B20
REFRESHED = frozenset({Step.REGULAR_REVIEW, Step.UNDRAFT, Step.MERGE})


def worker(task: Task, comment: str = "") -> Next:
    """A worker round.

    Args:
        task: what the worker does.
        comment: the address a FIX_EXECUTION round names (see ``Next.comment``).

    Returns:
        The step.
    """
    return Next(step=Step.WORKER, task=task, comment=comment)


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


def fix_ruling(comment: str) -> Next:
    """The step of a PR whose newest Opus ruling cannot be read.

    Args:
        comment: the address of that comment.

    Returns:
        The step.
    """
    return Next(step=Step.FIX_RULING, comment=comment)


def ruling_escalates() -> Next:
    """The step of a PR whose Opus ruling escalated to the owner.

    Returns:
        The step.
    """
    return Next(step=Step.RULING_ESCALATES)


def plan_edited() -> Next:
    """The step of a PR whose approved Plan was edited with no ruling.

    Returns:
        The step.
    """
    return Next(step=Step.PLAN_EDITED)


def plan_check() -> Next:
    """The step of a Plan that no recorded clean check covers.

    Returns:
        The step.
    """
    return Next(step=Step.PLAN_CHECK)


def run_e2e(branch: str) -> Next:
    """The step of a draft whose changed e2e suite has run in no check run.

    Args:
        branch: the head branch to dispatch the check workflow on.

    Returns:
        The step.
    """
    return Next(step=Step.RUN_E2E, branch=branch)


def merge() -> Next:
    """The step that merges.

    Returns:
        The step.
    """
    return Next(step=Step.MERGE)


class Pending(enum.Enum):
    """Why no actor takes a PR now; it is in no answer and is never printed.

    Attributes:
        OWNER: the PR is paused; the owner decides.
        UNDRAFT: approved, but the PR cannot be undrafted yet.
        CI: CI on the head has not finished.
        SHARED_RED: the PR's red check is red on others (keyword: shared-red).
        BLOCKER: the PR names an open blocker (keyword: blocked-by).
        HOLD: a runner-pressure hold withholds the merge or dispatch.
    """

    OWNER = enum.auto()
    UNDRAFT = enum.auto()
    CI = enum.auto()
    SHARED_RED = enum.auto()
    BLOCKER = enum.auto()
    HOLD = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Idle:
    """Nobody acts on the PR now (keyword: one-path: it is omitted, not said).

    Attributes:
        pending: why, for the settlers that read it.
        names: the open blockers (a BLOCKER), else empty.
    """

    pending: Pending
    names: str = ""


Move = Next | Idle
OWNER_PENDING = Idle(pending=Pending.OWNER)  # the owner decides; no actor takes it
UNDRAFT_PENDING = Idle(pending=Pending.UNDRAFT)  # the window is not clear yet


def ci_pending() -> Idle:
    """A head whose CI has not finished: nobody works or reviews meanwhile.

    Returns:
        The move.
    """
    return Idle(pending=Pending.CI)


def step_is(move: Move, wanted: AbstractSet[Step]) -> bool:
    """Whether a move is a step of a set.

    Args:
        move: the move.
        wanted: the steps.

    Returns:
        True for a step in the set; False for any other step and for an idle PR.
    """
    return isinstance(move, Next) and move.step in wanted


def pending_is(move: Move, wanted: Pending) -> bool:
    """Whether no actor takes a PR for one reason.

    Args:
        move: the move.
        wanted: the reason.

    Returns:
        True when the PR is idle for that reason.
    """
    return isinstance(move, Idle) and move.pending is wanted


def task_of(move: Move) -> Task | None:
    """The task of a worker's step.

    Args:
        move: the move.

    Returns:
        The task, or None for any other step and for an idle PR.
    """
    return move.task if isinstance(move, Next) else None


def step_of(move: Move) -> Step | None:
    """The step of a move.

    Args:
        move: the move.

    Returns:
        The step, or None for an idle PR.
    """
    return move.step if isinstance(move, Next) else None
