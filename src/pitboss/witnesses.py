"""A state the shipped decider gives each worker task, and the one after its effects.

pitboss#526 (keyword: progress): a step a worker is told to do must change what the
step was decided from. For each ``Task`` of ``workerselect.TABLE`` a witness is a PR
(or the facts the settlers read) at which the shipped decider chooses the task, and
the same PR after the worker did the effects the table requires of it. The decider
is run on both, never a copy of its rules.
"""

import dataclasses
from typing import AbstractSet, Callable, Mapping, Protocol, Sequence

from . import (
    blockedstep,
    bodydigest,
    flow,
    handbackderive,
    sharedstep,
    shapes,
    steps,
)
from . import witnessstates as ws
from .workerselect import TABLE, Effect, Task

Performed = AbstractSet[Effect]
APPROVED, CHANGES = ws.APPROVED, ws.CHANGES
BODY, HEAD = ws.BODY, ws.HEAD
REJECTED = (ws.FIRST_REJECTION, ws.SECOND_REJECTION)
PLAN_REJECTION = ws.graded(*ws.PLAN_REJECTED, 1)
PLAN_ONLY = ws.graded(APPROVED, None, 1)
QUOTES_PLAN = "## Plan\n1. CI quote: the Run Nox step of the head\n"
UNQUOTED = "## Execution\nthe work\n"
QUOTED = "## Execution\nCI quote: check.yml, job 5, step Run Nox, `3 passed`\n"
UNWRITTEN = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nNot started: later\n"
FINDING = "Finding: false statements in doc/index.rst\n"
Blockers = Mapping[str, blockedstep.Blocker]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Setting:
    """A PR and what its step is decided from besides it.

    Attributes:
        pr: the PR.
        known: the blockers its body names, by reference.
        groups: the failed checks it shares with other holders of its repository.
    """

    pr: flow.PullState
    known: Blockers
    groups: Sequence[sharedstep.Shared]


class Decider(Protocol):
    """What gives a PR and what its step is decided from, the step."""

    def __call__(self, setting: Setting) -> steps.Move | None:
        """The step.

        Args:
            setting: the PR, its blockers and its shared red.

        Returns:
            The step the shipped decider gives.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Witness:
    """The settings at which a task is chosen, and after its worker's effects.

    Attributes:
        before: the PR the decider gives the task.
        after: the PR after the effects the table requires of the task.
    """

    before: Setting
    after: Setting


def _alone(pr: flow.PullState) -> Setting:
    return Setting(pr=pr, known={}, groups=())


def _at(
    pr: flow.PullState, task: Task, effects: Performed, body: str | None = None
) -> Witness:
    done = applied(pr, task, body, effects)
    return Witness(before=_alone(pr), after=_alone(done))


NEW_HEAD = "f" * 40


def _rebodied(state: flow.PullState, body: str) -> flow.PullState:
    return dataclasses.replace(state, pull=dataclasses.replace(state.pull, body=body))


def _handed(state: flow.PullState) -> flow.PullState:
    body = ws.named_head(state.pull.body, state.pull.head.sha)
    pull = _rebodied(state, body).pull
    check = dataclasses.replace(
        ws.COMMENT,
        body=ws.clean_text(body),
        author_association=sorted(state.trusted)[0],
        created_at="2099-01-01T00:00:00Z",
    )
    comments = [*state.comments, check]
    derived = handbackderive.derive(pull, comments, state.trusted)
    again = dataclasses.replace(state, pull=pull, comments=comments)
    return ws.with_handed(again, derived)


def _written(
    state: flow.PullState, body: str | None, required: AbstractSet[Effect]
) -> flow.PullState:
    # the body the worker writes, when its effects edit it
    edits = bool({Effect.EDIT_BODY, Effect.EDIT_PLAN} & required)
    return _rebodied(state, body) if body and edits else state


def _pushed(state: flow.PullState, required: AbstractSet[Effect]) -> flow.PullState:
    if Effect.PUSH not in required:
        return state
    head = dataclasses.replace(state.pull.head, sha=NEW_HEAD)
    # GitHub reads a pushed head afresh: no conflict, no check run yet
    clean = dataclasses.replace(state.pull, mergeable_state=shapes.MergeState.CLEAN)
    pull = dataclasses.replace(clean, head=head)
    return dataclasses.replace(state, pull=pull, checks=())


def applied(
    state: flow.PullState,
    task: Task,
    body: str | None = None,
    effects: AbstractSet[Effect] | None = None,
) -> flow.PullState:
    """The PR after a worker did the effects its task requires.

    A ticket filed is outside the PR (``workerselect.OUTSIDE``), so it changes
    nothing here.

    Args:
        state: the PR.
        task: the worker's task.
        body: the body the worker writes, when the task edits it.
        effects: what the worker does, the table's required effects of the task
            when not given (a proof gives the effects of a table it was handed).

    Returns:
        The PR.
    """
    required = TABLE[task].required if effects is None else effects
    pushed = _pushed(_written(state, body, required), required)
    return _handed(pushed) if Effect.HAND_BACK in required else pushed


def _rejecting(body: str) -> flow.PullState:
    # a rejection of the Plan that read this body, as a review records it
    named = bodydigest.digest(ws.with_head_line(body, HEAD))
    rejection = dataclasses.replace(
        PLAN_REJECTION, plan_digest=ws.digest(body), body=named
    )
    return ws.state(rejection)


def _ruled(word: str) -> flow.PullState:
    ruling = ws.ruling(5, line=f"Ruling: {word}")
    return ws.state(*REJECTED, comments=[ruling])


def _findings() -> flow.PullState:
    said = dataclasses.replace(
        ws.COMMENT,
        body=FINDING,
        author_association="MEMBER",
        created_at="2026-10-30T00:00:01Z",
        url="https://x.org/r",
    )
    return ws.state(ws.graded(CHANGES, None, 1), comments=[said])


def _restore(effects: Performed) -> Witness:
    # the Plan edited after its approval, a ruling stands and a push followed it
    edited = BODY.replace("the plan", "the plan, edited")
    read = ws.graded(*ws.EXECUTION_REJECTED, 1)
    review = dataclasses.replace(read, plan_digest=ws.digest(BODY))
    pushed = dataclasses.replace(ws.GREEN, started_at="2026-10-30T00:00:09Z")
    pr = ws.state(review, comments=[ws.ruling(2)], checks=[pushed], body=edited)
    return _at(pr, Task.RESTORE_PLAN, effects, BODY)


def _execution() -> flow.PullState:
    first = ws.graded(*ws.EXECUTION_REJECTED, 1, sha=ws.OLDER)
    return ws.state(first, ws.graded(None, CHANGES, 3), comments=[ws.ruling(2)])


def _stale(effects: Performed) -> Witness:
    current = f"{BODY}\nHead: {HEAD}\n"
    older = f"{BODY}\nHead: {'b' * 40}\n"
    return _at(ws.state(body=older), Task.REFRESH_BODY, effects, current)


def _quotes(effects: Performed) -> Witness:
    unquoted = ws.state(PLAN_ONLY, body=f"Fixes #7\n\n{QUOTES_PLAN}\n{UNQUOTED}")
    body = f"Fixes #7\n\n{QUOTES_PLAN}\n{QUOTED}"
    return _at(unquoted, Task.ADD_CI_QUOTES, effects, body)


def _owed(pr: flow.PullState) -> flow.PullState:
    # no hand-back yet: the body names no head under a clean check, none was posted
    return ws.with_handed(pr, handbackderive.derive(pr.pull, [], pr.trusted))


def _handed_back(effects: Performed) -> Witness:
    owed = _owed(ws.state())
    return _at(owed, Task.HAND_BACK, effects)


def _blocker(ref: str, state: blockedstep.State, merged: str = "") -> Blockers:
    each = blockedstep.Blocker(reference=ref, state=state, merged_at=merged, body="")
    return {ref: each}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Waits:
    """What a PR waits for, before and after its worker's effects.

    Attributes:
        before: the blockers the PR's body names, by reference.
        body: the body the worker writes.
        after: the blockers the written body names, by reference.
    """

    before: Blockers
    body: str
    after: Blockers


def _settling(pr: flow.PullState, task: Task, did: Performed, waits: Waits) -> Witness:
    # the same PR before and after the worker's effects, given its blockers
    mine = f"{ws.REPOSITORY}#{pr.pull.number}"
    shared = sharedstep.Shared(
        slug=ws.REPOSITORY, check="c", line="boom", holders=[mine, "o/r#99"]
    )
    done = applied(pr, task, waits.body, did)
    return Witness(
        before=Setting(pr=pr, known=waits.before, groups=[shared]),
        after=Setting(pr=done, known=waits.after, groups=[shared]),
    )


RED = ws.state(checks=(ws.RED,))
WAITING = "o/r#1125"
NAMED = f"{BODY}\nBlocked-by: {WAITING}\n"
OPEN = blockedstep.State.OPEN


def _shared(effects: Performed) -> Witness:
    # the PR names the ticket in a Blocked-by line: the shared red is not read
    body = f"{RED.pull.body}\nBlocked-by: o/r#99\n"
    waits = Waits(before={}, body=body, after=_blocker("o/r#99", OPEN))
    return _settling(RED, Task.SHARED_RED, effects, waits)


def _closed(effects: Performed) -> Witness:
    shut = _blocker(WAITING, blockedstep.State.CLOSED)
    named = ws.state(body=NAMED)
    return _settling(
        named, Task.FIX_BLOCKED_BY, effects, Waits(before=shut, body=BODY, after=shut)
    )


def _merged(effects: Performed) -> Witness:
    # the red check ended before the blocker merged: a push ends it
    early = dataclasses.replace(ws.RED, completed_at="2026-11-24T04:00:00Z")
    done = _blocker(WAITING, blockedstep.State.MERGED, "2026-11-24T05:00:00Z")
    red = ws.state(checks=(early,), body=NAMED)
    return _settling(
        red, Task.AFTER_BLOCKER, effects, Waits(before=done, body="", after=done)
    )


def _partial(effects: Performed) -> Witness:
    bare = ws.state()
    kept = [each for each in bare.comments if not each.body.startswith("Plan check")]
    pr = dataclasses.replace(bare, comments=kept)
    return _at(pr, Task.FINISH_PARTIAL, effects)


def _of(
    pr: Callable[[], flow.PullState], task: Task, body: str | None = None
) -> Callable[[Performed], Witness]:
    return lambda effects: _at(pr(), task, effects, body)


EDITED = BODY.replace("the plan", "the plan, edited")
BUILDERS: Mapping[Task, Callable[[Performed], Witness]] = {
    Task.FIRST_ROUND: _of(lambda: ws.state(body=""), Task.FIRST_ROUND, BODY),
    Task.FIX_CI: _of(lambda: RED, Task.FIX_CI),
    Task.REVISE_PLAN: _of(lambda: _rejecting(BODY), Task.REVISE_PLAN, EDITED),
    Task.RESTORE_PLAN: _restore,
    Task.RESOLVE_CONFLICT: _of(
        lambda: ws.state(mergeable_state="dirty"), Task.RESOLVE_CONFLICT
    ),
    Task.FIX_EXECUTION: _of(_execution, Task.FIX_EXECUTION),
    Task.RULING_STEPS: _of(lambda: _ruled("do these steps"), Task.RULING_STEPS),
    Task.RULING_AS_GIVEN: _of(lambda: _ruled("split"), Task.RULING_AS_GIVEN),
    Task.RUN_PLAN: _of(
        lambda: ws.state(PLAN_ONLY, body=UNWRITTEN), Task.RUN_PLAN, BODY
    ),
    Task.ADD_CI_QUOTES: _quotes,
    Task.FIX_ROUND: _of(_findings, Task.FIX_ROUND),
    Task.REFRESH_BODY: _stale,
    Task.SHARED_RED: _shared,
    Task.FIX_BLOCKED_BY: _closed,
    Task.AFTER_BLOCKER: _merged,
    Task.FINISH_PARTIAL: _partial,
    Task.HAND_BACK: _handed_back,
}


def of(task: Task, effects: Performed) -> Witness:
    """The witness of a task, for the effects its worker is taken to do.

    Args:
        task: the task.
        effects: what its worker does (the table's, or a table a proof was given).

    Returns:
        The witness.
    """
    return BUILDERS[task](effects)


def stuck(each: Witness, decided: Decider) -> bool:
    """Whether the PR is left at a worker (the task's or another's).

    Args:
        each: a witness.
        decided: the shipped decider.

    Returns:
        True when the step after is none, the step before, or a worker's: a PR that
        a worker's effects leave to a worker (the same or another) is not shown to
        have moved on.
    """
    after = decided(each.after)
    return (
        after is None
        or after == decided(each.before)
        or steps.task_of(after) is not None
    )


WITNESSES: Mapping[Task, Witness] = {
    task: of(task, entry.required) for task, entry in TABLE.items()
}
