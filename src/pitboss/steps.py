"""The steps of the review flow of a PR (keyword: review-flow).

A step says what happens next to a PR: who acts and on what. ``flow.next_step``
gives one; ``describe`` says it in a line.
"""

import dataclasses
import enum
from typing import Mapping

PAUSED_LABEL = "paused-owner"
RULING_FIRST_LINE = "Opus ruling"
PLAN_CHECK_FIRST_LINE = "Plan check"  # keyword: plan-check (pitboss#192)
PLAN_CHECK_OK = "Plan check: ok"
RUN_E2E_MARKER = "RUN E2E BEFORE APPROVAL"  # keyword: run-e2e (pitboss#199)
# keyword: owner-artifact (pitboss#237, the owner's standing ruling of 2026-11-04)
OWNER_ARTIFACT = (
    "attach a markdown artifact with the sections 'What happened',"
    " 'Recommendation' and 'Suggested mitigation'"
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
        WAIT_FOR_OWNER: the PR is paused; the owner decides.
        WORKER: a worker does a task.
        UNDRAFT: mark the PR ready (a draft approved at its head, pitboss#176).
        REGULAR_REVIEW: a new reviewer grades a stage.
        WAIT_FOR_UNDRAFT: approved, but the PR cannot be undrafted yet.
        WAIT_FOR_CI: CI on the head has not finished; nobody works meanwhile.
        OPUS_RULING: one Opus agent makes a binding ruling.
        PAUSE_FOR_OWNER: pause the PR and tell the owner the options.
        FIX_RULING: the newest Opus ruling has no readable ``Ruling:`` line.
        RULING_ESCALATES: the Opus ruling escalated to the owner.
        PLAN_EDITED: the Plan differs from the one an approving review read, and
            no Opus ruling authorises the edit (keyword: plan-digest, pitboss#172).
        PLAN_CHECK: no trusted comment records a clean ``pitboss plan-check`` of
            this Plan (keyword: plan-check, pitboss#192); no review first.
        SEND_BACK_PLAN_CHECK: the newest Plan check refused the Plan; the pushing
            worker sends it back, no round (pitboss#471).
        RUN_E2E: a draft with an approved Plan, whose diff touches what the e2e
            suite runs on, has no completed dispatched ``check.yml`` run at its
            head (its own run skipped e2e): dispatch it on its branch before any
            approval (keyword: run-e2e, pitboss#199).
        WAIT_FOR_HOLD: a runner-pressure hold withholds the merge or dispatch.
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
    FIX_RULING = enum.auto()
    RULING_ESCALATES = enum.auto()
    PLAN_EDITED = enum.auto()
    PLAN_CHECK = enum.auto()
    SEND_BACK_PLAN_CHECK = enum.auto()
    RUN_E2E = enum.auto()
    WAIT_FOR_HOLD = enum.auto()
    MERGE = enum.auto()


class Task(enum.Enum):
    """What a worker is told to do; the value is the text.

    Attributes:
        FIRST_ROUND: the first work on a PR with no Plan and Execution body.
        FIX_CI: the head's CI is red.
        REVISE_PLAN: the plan alone, no code.
        RESOLVE_CONFLICT: the head conflicts with the base, at any stage but a
            wait (``WAITS``, including PLAN_EDITED).
        FIX_EXECUTION: the execution, against the approved plan.
        RULING_STEPS: exactly the steps of an Opus ruling.
        RULING_AS_GIVEN: what an Opus ruling says to the ticket and the PR.
        RUN_PLAN: the Plan was approved alone after a ruling, or the Execution is
            empty or a placeholder (keyword: unwritten-execution, pitboss#294,
            plan-alone, pitboss#201): run its commands as written.
        ADD_CI_QUOTES: the Plan has CI-quote rows and the body lacks the quotes,
            which exist only after the PR is ready and its checks pass (keyword:
            ci-quotes, pitboss#277).
        FIX_ROUND: findings name a file of the tree: code, doc, test may change
            (keyword: fix-round-kind).
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
    RUN_PLAN = (
        "run the approved Plan's commands as written and fill the Execution"
        " (the Plan was approved alone, after a ruling, or the Execution section"
        " is empty or a placeholder)"
    )
    ADD_CI_QUOTES = "add the CI quotes to the body"
    FIX_ROUND = "fix round: fix the findings, each one (code, doc, test, Plan)"


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


# the steps at which a PR waits for an Opus ruling or the owner (pitboss#148), or
# for an edited approved Plan to be restored or ruled (pitboss#172): a conflict
# is not resolved meanwhile, and the sweep prints a line for each
WAITS = frozenset(
    {
        Step.OPUS_RULING,
        Step.PAUSE_FOR_OWNER,
        Step.RULING_ESCALATES,
        Step.PLAN_EDITED,
    }
)
HELD = frozenset({Step.MERGE, Step.RUN_E2E})  # keyword: hold-scope, B20
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
        " disagreed about, the options and a `How we got here` section, and report"
        " the number and the options to the owner on a card that has the section"
        f" and, on the card, {OWNER_ARTIFACT}"
    ),
    Step.FIX_RULING: (
        "the newest Opus ruling has no readable `Ruling:` second line; an agent"
        " edits or reposts the comment; no Opus agent is asked for"
    ),
    Step.RULING_ESCALATES: (
        "the Opus ruling escalated to the owner: label the PR and its ticket"
        f" {PAUSED_LABEL}, comment the options and a `How we got here` section,"
        " and report the number and the options to the owner on a card that has"
        f" the section and, on the card, {OWNER_ARTIFACT}"
    ),
    Step.PLAN_EDITED: (
        "the Plan was edited after its approval: restore the approved Plan, or"
        " ask an Opus agent for a ruling that says `revise the plan`; no review"
        " or fix is offered meanwhile"
    ),
    Step.PLAN_CHECK: (
        "post the Plan check: run `uvx pitboss plan-check <body file>` on the PR"
        " body and post its whole"
        f" output as a PR comment (its first line is {PLAN_CHECK_FIRST_LINE!r});"
        " the Plan review is offered once it says `Plan check: ok` for this Plan"
    ),
    Step.SEND_BACK_PLAN_CHECK: (
        "the Plan check is refused ({comment}): the worker that pushed the PR"
        " sends back the posted check; this is no fix round: {findings}"
    ),
    Step.RUN_E2E: f"{RUN_E2E_MARKER}: dispatch check.yml on {{branch}}",
    Step.WAIT_FOR_HOLD: "HOLD: a runner-pressure hold withholds this merge or dispatch",
    Step.MERGE: "CI is green and there is no conflict: arm auto-merge or merge",
}


# keyword: fixed-on-base (pitboss#314): the words of a red CI the base has answered
ENQUEUE = "enqueue it (the merge queue tests it on main)"
REQUEST_REVIEW = "request the review"


def describe(step: Next) -> str:
    """Say what to do for a step, in one line.

    Args:
        step: the step.

    Returns:
        Its task, its stage, or the text of the step.
    """
    if step.step is Step.MERGE and step.on_base:
        return ENQUEUE
    if step.task is not None:
        return step.task.value
    if step.stage is not None and step.on_base:
        return f"{REQUEST_REVIEW}: {step.stage.value}"
    if step.stage is not None:
        return step.stage.value
    return TEXTS[step.step].format_map(dataclasses.asdict(step))


def wait_for_owner() -> Next:
    """The step of a PR paused for the owner.

    Returns:
        The step.
    """
    return Next(step=Step.WAIT_FOR_OWNER)


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
