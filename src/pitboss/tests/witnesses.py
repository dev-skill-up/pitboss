"""A state the shipped decider gives each worker task, and the one after its effects.

pitboss#526 (keyword: progress): a step a worker is told to do must change what the
step was decided from. For each ``Task`` of ``workerselect.TABLE`` a witness is a PR
(or the facts the settlers read) at which the shipped decider chooses the task, and
the same PR after the worker did the effects the table requires of it. The decider
is run on both, never a copy of its rules.
"""

import dataclasses
import functools
from typing import AbstractSet, Callable, Mapping, Sequence

from .. import (
    blockedby,
    blockedstep,
    bodydigest,
    config,
    finishstep,
    flow,
    headsignals,
    pullfacts,
    pullref,
    rounds,
    sharedstep,
    steps,
    straycomments,
    reviews,
)
from ..workerselect import TABLE, Effect, Task
from . import blank, corpuseffects, derivedhand, headed, pullstates
from . import test_flow as sample
from .test_plan_digest_collapse import digest

Decide = Callable[[], steps.Move | None]
Performed = AbstractSet[Effect]
APPROVED, CHANGES = sample.APPROVED, sample.CHANGES
BODY, HEAD = sample.BODY, sample.HEAD
REJECTED = (sample.FIRST_REJECTION, sample.SECOND_REJECTION)
PLAN_REJECTION = sample.graded(*sample.PLAN_REJECTED, 1)
PLAN_ONLY = sample.graded(APPROVED, None, 1)
QUOTES_PLAN = "## Plan\n1. CI quote: the Run Nox step of the head\n"
UNQUOTED = "## Execution\nthe work\n"
QUOTED = "## Execution\nCI quote: check.yml, job 5, step Run Nox, `3 passed`\n"
UNWRITTEN = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nNot started: later\n"
FINDING = "Finding: false statements in doc/index.rst\n"
Blockers = Mapping[str, blockedstep.Blocker]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Witness:
    """The decider's step at a PR, and at the PR after its worker's effects.

    Attributes:
        before: the step at the PR.
        after: the step at the PR after the effects the table requires of the task.
    """

    before: Decide
    after: Decide


def _at(
    pr: flow.PullState, task: Task, effects: Performed, body: str | None = None
) -> Witness:
    done = corpuseffects.applied(pr, task, body, effects)
    return Witness(
        before=lambda: flow.next_step(pr), after=lambda: flow.next_step(done)
    )


def _rejecting(body: str) -> flow.PullState:
    # a rejection of the Plan that read this body, as a review records it
    named = bodydigest.digest(headed.with_head_line(body, HEAD))
    rejection = dataclasses.replace(
        PLAN_REJECTION, plan_digest=digest(body), body=named
    )
    return sample.state(rejection)


def _ruled(word: str) -> flow.PullState:
    ruling = sample.ruling(5, line=f"Ruling: {word}")
    return sample.state(*REJECTED, comments=[ruling])


def _findings() -> flow.PullState:
    said = dataclasses.replace(
        blank.COMMENT,
        body=FINDING,
        author_association="MEMBER",
        created_at="2026-10-30T00:00:01Z",
        url="https://x.org/r",
    )
    return sample.state(sample.graded(CHANGES, None, 1), comments=[said])


def _restore(effects: Performed) -> Witness:
    # the Plan edited after its approval, a ruling stands and a push followed it
    edited = BODY.replace("the plan", "the plan, edited")
    read = sample.graded(*sample.EXECUTION_REJECTED, 1)
    review = dataclasses.replace(read, plan_digest=digest(BODY))
    pushed = dataclasses.replace(sample.GREEN, started_at="2026-10-30T00:00:09Z")
    pr = sample.state(review, comments=[sample.ruling(2)], checks=[pushed], body=edited)
    return _at(pr, Task.RESTORE_PLAN, effects, BODY)


def _execution() -> flow.PullState:
    first = sample.graded(*sample.EXECUTION_REJECTED, 1, sha=sample.OLDER)
    return sample.state(
        first, sample.graded(None, CHANGES, 3), comments=[sample.ruling(2)]
    )


def _stale(effects: Performed) -> Witness:
    current = f"{BODY}\nHead: {HEAD}\n"
    older = f"{BODY}\nHead: {'b' * 40}\n"
    return _at(sample.state(body=older), Task.REFRESH_BODY, effects, current)


def _quotes(effects: Performed) -> Witness:
    unquoted = sample.state(PLAN_ONLY, body=f"Fixes #7\n\n{QUOTES_PLAN}\n{UNQUOTED}")
    body = f"Fixes #7\n\n{QUOTES_PLAN}\n{QUOTED}"
    return _at(unquoted, Task.ADD_CI_QUOTES, effects, body)


def _handed_back(effects: Performed) -> Witness:
    owed = pullstates.with_recorded(sample.state(), handed=derivedhand.held())
    return _at(owed, Task.HAND_BACK, effects)


def _facts(pr: flow.PullState) -> pullfacts.PullFacts:
    # the facts the settlers read of a PR, at the step the flow gives it
    build = functools.partial(
        pullfacts.PullFacts,
        repo=config.make_repo("o", "r"),
        pull=pr.pull,
        checks=pr.checks,
        review=None,
        standing=reviews.Standing.NONE,
        signals=headsignals.NONE,
        unreadable=straycomments.NONE,
    )
    return build(step=flow.next_step(pr), review_rounds=rounds.NONE, relock=False)


def _blocker(ref: str, state: blockedstep.State, merged: str = "") -> Blockers:
    each = blockedstep.Blocker(reference=ref, state=state, merged_at=merged, body="")
    return {ref: each}


def _settled(
    pr: flow.PullState, known: Blockers, groups: Sequence[sharedstep.Shared] = ()
) -> steps.Move | None:
    # the step the settlers give a PR: its blockers (those its body names), then a
    # shared red, then its own
    facts = _facts(pr)
    named = [known[each] for each in blockedby.declared(facts)]
    return (
        blockedstep.verdict(facts, named)
        or sharedstep.stepped(facts, groups)
        or facts.step
    )


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
    mine = pullref.reference(_facts(pr))
    shared = sharedstep.Shared(
        slug="o/r", check="c", line="boom", holders=[mine, "o/r#99"]
    )
    done = corpuseffects.applied(pr, task, waits.body, did)
    return Witness(
        before=lambda: _settled(pr, waits.before, [shared]),
        after=lambda: _settled(done, waits.after, [shared]),
    )


RED = sample.state(checks=(sample.RED,))
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
    named = sample.state(body=NAMED)
    return _settling(
        named, Task.FIX_BLOCKED_BY, effects, Waits(before=shut, body=BODY, after=shut)
    )


def _merged(effects: Performed) -> Witness:
    # the red check ended before the blocker merged: a push ends it
    early = dataclasses.replace(sample.RED, completed_at="2026-11-24T04:00:00Z")
    done = _blocker(WAITING, blockedstep.State.MERGED, "2026-11-24T05:00:00Z")
    red = sample.state(checks=(early,), body=NAMED)
    return _settling(
        red, Task.AFTER_BLOCKER, effects, Waits(before=done, body="", after=done)
    )


def _partial(effects: Performed) -> Witness:
    bare = sample.state()
    kept = [each for each in bare.comments if not each.body.startswith("Plan check")]
    pr = dataclasses.replace(bare, comments=kept)
    done = corpuseffects.applied(pr, Task.FINISH_PARTIAL, None, effects)

    def finish(at: flow.PullState) -> steps.Move | None:
        return finishstep.step_of(_facts(at)) or flow.next_step(at)

    return Witness(before=lambda: finish(pr), after=lambda: finish(done))


def _of(
    pr: Callable[[], flow.PullState], task: Task, body: str | None = None
) -> Callable[[Performed], Witness]:
    return lambda effects: _at(pr(), task, effects, body)


EDITED = BODY.replace("the plan", "the plan, edited")
BUILDERS: Mapping[Task, Callable[[Performed], Witness]] = {
    Task.FIRST_ROUND: _of(lambda: sample.state(body=""), Task.FIRST_ROUND, BODY),
    Task.FIX_CI: _of(lambda: RED, Task.FIX_CI),
    Task.REVISE_PLAN: _of(lambda: _rejecting(BODY), Task.REVISE_PLAN, EDITED),
    Task.RESTORE_PLAN: _restore,
    Task.RESOLVE_CONFLICT: _of(
        lambda: sample.state(mergeable_state="dirty"), Task.RESOLVE_CONFLICT
    ),
    Task.FIX_EXECUTION: _of(_execution, Task.FIX_EXECUTION),
    Task.RULING_STEPS: _of(lambda: _ruled("do these steps"), Task.RULING_STEPS),
    Task.RULING_AS_GIVEN: _of(lambda: _ruled("split"), Task.RULING_AS_GIVEN),
    Task.RUN_PLAN: _of(
        lambda: sample.state(PLAN_ONLY, body=UNWRITTEN), Task.RUN_PLAN, BODY
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


def stuck(each: Witness) -> bool:
    """Whether the PR is left at a worker (the task's or another's).

    Args:
        each: a witness.

    Returns:
        True when the step after is none, the step before, or a worker's: a PR that
        a worker's effects leave to a worker (the same or another) is not shown to
        have moved on.
    """
    after = each.after()
    return after is None or after == each.before() or steps.task_of(after) is not None


WITNESSES: Mapping[Task, Witness] = {
    task: of(task, entry.required) for task, entry in TABLE.items()
}
