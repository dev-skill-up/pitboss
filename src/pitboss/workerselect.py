"""The one table of what selects a worker task (keyword: worker-select).

pitboss#526: a task is selected by a fact of the PR, and the worker's action must be
able to change that fact, else the PR is chosen for the same task forever (bats-lang
/dom#140). Each ``Selector`` says which facts its task is decided from (``reads``)
and which its action changes (``writes``); a text the task reads is judged by the
body's words, so it also names the fact that ends it when no edit makes the words
show (``ends_by``). Every worker step is built by ``steps.worker`` from this
table, and P13.3 (``selectorproofs``) proves the table.
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


class Fact(enum.Enum):
    """What a PR shows that a step is decided from.

    Attributes:
        HEAD: the head commit.
        CHECKS: the check runs of the head.
        CONFLICT: whether the head conflicts with the base.
        REVIEWS: the reviews that count for the head and the body.
        BODY: the PR body.
        TEXT: the literal words of the body, judged against a ruling.
        APPLIED: whether a ruling is applied.
        HANDBACK: the worker's hand-back of the head and body.
        TICKET: the ticket a shared red files.
    """

    HEAD = enum.auto()
    CHECKS = enum.auto()
    CONFLICT = enum.auto()
    REVIEWS = enum.auto()
    BODY = enum.auto()
    TEXT = enum.auto()
    APPLIED = enum.auto()
    HANDBACK = enum.auto()
    TICKET = enum.auto()


# a push changes the head, and with it what the head's checks, conflict and reviews are
PUSH = frozenset({Fact.HEAD, Fact.CHECKS, Fact.CONFLICT, Fact.REVIEWS})
# a body edit changes what a review of the body was of
EDIT = frozenset({Fact.BODY, Fact.REVIEWS})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Selector:
    """One task: what selects it and what its action changes.

    Attributes:
        task: the task.
        reads: the facts it is selected by.
        writes: the facts its action changes.
        ends_by: the fact that ends it when the text it reads cannot be made to
            show, None when it reads no text.
    """

    task: Task
    reads: AbstractSet[Fact]
    writes: AbstractSet[Fact]
    ends_by: Fact | None = None


def _of(
    task: Task,
    reads: AbstractSet[Fact],
    writes: AbstractSet[Fact],
    ends_by: Fact | None = None,
) -> tuple[Task, Selector]:
    return task, Selector(
        task=task, reads=frozenset(reads), writes=writes, ends_by=ends_by
    )


TABLE: Mapping[Task, Selector] = dict(
    [
        _of(Task.FIRST_ROUND, {Fact.BODY}, EDIT | PUSH),
        _of(Task.FIX_CI, {Fact.CHECKS}, PUSH),
        _of(Task.REVISE_PLAN, {Fact.REVIEWS}, EDIT),
        _of(Task.RESTORE_PLAN, {Fact.BODY}, EDIT),
        _of(Task.RESOLVE_CONFLICT, {Fact.CONFLICT}, PUSH),
        _of(Task.FIX_EXECUTION, {Fact.REVIEWS}, PUSH),
        _of(
            Task.RULING_STEPS,
            {Fact.APPLIED, Fact.TEXT},
            PUSH | EDIT | {Fact.HANDBACK, Fact.APPLIED},
            Fact.REVIEWS,
        ),
        _of(Task.RULING_AS_GIVEN, {Fact.APPLIED}, PUSH | EDIT | {Fact.APPLIED}),
        _of(Task.RUN_PLAN, {Fact.BODY}, EDIT),
        _of(Task.ADD_CI_QUOTES, {Fact.BODY}, EDIT),
        _of(Task.FIX_ROUND, {Fact.REVIEWS}, PUSH),
        _of(Task.REFRESH_BODY, {Fact.BODY, Fact.HEAD}, EDIT),
        _of(Task.SHARED_RED, {Fact.CHECKS, Fact.TICKET}, frozenset({Fact.TICKET})),
        _of(Task.FIX_BLOCKED_BY, {Fact.BODY}, EDIT),
        _of(Task.AFTER_BLOCKER, {Fact.CHECKS}, PUSH),
        _of(Task.FINISH_PARTIAL, {Fact.HANDBACK}, frozenset({Fact.HANDBACK})),
        _of(Task.HAND_BACK, {Fact.HANDBACK}, frozenset({Fact.HANDBACK})),
    ]
)
