"""The one table of what selects a worker task (keyword: worker-select).

pitboss#526: a task is selected by a fact of the PR, and the worker's action must be
able to change that fact, else the PR is chosen for the same task forever (bats-lang
/dom#140). Each ``Selector`` says which facts its task is decided from (``reads``)
and which its action changes (``writes``); a text the task reads is judged by the
body's words, so it also names the fact that ends it when no edit makes the words
show (``ends_by``). Every worker step is built by ``worker`` here, and P13.3
(``selectorproofs``) proves the table.
"""

import dataclasses
import enum
from typing import Mapping

from . import steps


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


@dataclasses.dataclass(frozen=True, slots=True)
class Selector:
    """One task: what selects it and what its action changes.

    Attributes:
        task: the task.
        reads: the facts it is selected by.
        writes: the facts its action changes.
        ends_by: the fact that ends it when the text it reads cannot be made to
            show, None when it reads no text.
    """

    task: steps.Task
    reads: frozenset[Fact]
    writes: frozenset[Fact]
    ends_by: Fact | None = None


def _of(
    task: steps.Task,
    reads: set[Fact],
    writes: frozenset[Fact],
    ends_by: Fact | None = None,
) -> tuple[steps.Task, Selector]:
    return task, Selector(task, frozenset(reads), writes, ends_by)


TABLE: Mapping[steps.Task, Selector] = dict(
    [
        _of(steps.Task.FIRST_ROUND, {Fact.BODY}, EDIT | PUSH),
        _of(steps.Task.FIX_CI, {Fact.CHECKS}, PUSH),
        _of(steps.Task.REVISE_PLAN, {Fact.REVIEWS}, EDIT),
        _of(steps.Task.RESTORE_PLAN, {Fact.BODY}, EDIT),
        _of(steps.Task.RESOLVE_CONFLICT, {Fact.CONFLICT}, PUSH),
        _of(steps.Task.FIX_EXECUTION, {Fact.REVIEWS}, PUSH),
        _of(
            steps.Task.RULING_STEPS,
            {Fact.APPLIED, Fact.TEXT},
            PUSH | EDIT | {Fact.HANDBACK, Fact.APPLIED},
            Fact.REVIEWS,
        ),
        _of(steps.Task.RULING_AS_GIVEN, {Fact.APPLIED}, PUSH | EDIT | {Fact.APPLIED}),
        _of(steps.Task.RUN_PLAN, {Fact.BODY}, EDIT),
        _of(steps.Task.ADD_CI_QUOTES, {Fact.BODY}, EDIT),
        _of(steps.Task.FIX_ROUND, {Fact.REVIEWS}, PUSH),
        _of(steps.Task.REFRESH_BODY, {Fact.BODY, Fact.HEAD}, EDIT),
        _of(
            steps.Task.SHARED_RED, {Fact.CHECKS, Fact.TICKET}, frozenset({Fact.TICKET})
        ),
        _of(steps.Task.FIX_BLOCKED_BY, {Fact.BODY}, EDIT),
        _of(steps.Task.AFTER_BLOCKER, {Fact.CHECKS}, PUSH),
        _of(steps.Task.FINISH_PARTIAL, {Fact.HANDBACK}, frozenset({Fact.HANDBACK})),
        _of(steps.Task.HAND_BACK, {Fact.HANDBACK}, frozenset({Fact.HANDBACK})),
    ]
)


def worker(task: steps.Task, comment: str = "") -> steps.Next:
    """A worker round, built from the table's entry for the task.

    Args:
        task: what the worker does.
        comment: the address a FIX_EXECUTION round names.

    Returns:
        The step.
    """
    return steps.worker(TABLE[task].task, comment)
