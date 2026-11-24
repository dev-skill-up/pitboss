"""What each worker task may do and must do, as one typed table (worker-select).

pitboss#526 (bats-lang/dom#140): a task chosen again after its worker did what it
was told is a dead end. Each ``Selector`` says which ``Effect`` a worker of the task
may have on the PR (``allowed``) and which it must have to be done (``required``).
The brief's push sentences are made from ``allowed`` (``brief``), and the progress
property (``tests.test_properties``) applies ``required`` to every state the flow
gives the task and wants the flow to give another step. Every worker step is built
by ``steps.worker`` from this table, and P13.3 (``selectorproofs``) proves it.
"""

import dataclasses
import enum
from typing import AbstractSet, Mapping


class Task(enum.Enum):
    """What a worker is told to do; the value is the text.

    Attributes:
        FIRST_ROUND: the first work on a PR with no Plan and Execution body.
        FIX_CI: the head's CI is red.
        REVISE_PLAN: the plan alone, no code.
        RESTORE_PLAN: put the approved Plan back, an Opus ruling already stands.
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
        HAND_BACK: the head and body were not handed back (keyword: standing).
    """

    FIRST_ROUND = "fix as best it can and write Plan and Execution in the body"
    FIX_CI = "fix CI on the head (a red CI is never a rejection)"
    REVISE_PLAN = "revise the PLAN only, change no code"
    RESTORE_PLAN = "restore the approved Plan in the body, change no code"
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
    HAND_BACK = (
        "hand this head and body back: run `pitboss hand-back-check` on the current"
        " head and body (every check it makes must pass); no review is offered"
        " before"
    )


class Effect(enum.Enum):
    """What a worker does to a PR.

    Attributes:
        PUSH: pushes commits to the head branch.
        EDIT_BODY: edits the PR body.
        EDIT_PLAN: changes the Plan section of the PR body.
        HAND_BACK: names the head in the body's ``Head:`` line and has a clean Plan
            check posted for it.
        FILE_TICKET: files or extends a ticket.
    """

    PUSH = enum.auto()
    EDIT_BODY = enum.auto()
    EDIT_PLAN = enum.auto()
    HAND_BACK = enum.auto()
    FILE_TICKET = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Selector:
    """One task: what its worker may do and must do.

    Attributes:
        task: the task.
        allowed: the effects its brief allows.
        required: the effects that make it done.
    """

    task: Task
    allowed: AbstractSet[Effect]
    required: AbstractSet[Effect]


def _of(
    task: Task, required: AbstractSet[Effect], allowed: AbstractSet[Effect]
) -> tuple[Task, Selector]:
    return task, Selector(task=task, allowed=allowed | required, required=required)


PUSHES = frozenset({Effect.PUSH, Effect.EDIT_BODY, Effect.HAND_BACK})
BODY_ONLY = frozenset({Effect.EDIT_BODY, Effect.HAND_BACK})
PLAN_BODY = BODY_ONLY | {Effect.EDIT_PLAN}
BACK = frozenset({Effect.HAND_BACK})
TICKET = frozenset({Effect.FILE_TICKET})
PUSH_THEN_BACK = frozenset({Effect.PUSH, Effect.HAND_BACK})

TABLE: Mapping[Task, Selector] = dict(
    [
        _of(Task.FIRST_ROUND, BODY_ONLY, PUSHES),
        _of(Task.FIX_CI, PUSH_THEN_BACK, PUSHES),
        _of(Task.REVISE_PLAN, PLAN_BODY, PLAN_BODY),
        _of(Task.RESTORE_PLAN, PLAN_BODY, PLAN_BODY),
        _of(Task.RESOLVE_CONFLICT, PUSH_THEN_BACK, PUSHES),
        _of(Task.FIX_EXECUTION, PUSH_THEN_BACK, PUSHES),
        _of(Task.RULING_STEPS, BACK, PUSHES),
        _of(Task.RULING_AS_GIVEN, BACK, PUSHES | TICKET),
        _of(Task.RUN_PLAN, BODY_ONLY, PUSHES),
        _of(Task.ADD_CI_QUOTES, BODY_ONLY, PUSHES),
        _of(Task.FIX_ROUND, PUSH_THEN_BACK, PUSHES),
        _of(Task.REFRESH_BODY, BODY_ONLY, BODY_ONLY),
        _of(Task.SHARED_RED, TICKET, TICKET),
        _of(Task.FIX_BLOCKED_BY, BODY_ONLY, BODY_ONLY),
        _of(Task.AFTER_BLOCKER, PUSH_THEN_BACK, PUSHES),
        _of(Task.FINISH_PARTIAL, BACK, PUSHES),
        _of(Task.HAND_BACK, BACK, BACK),
    ]
)
