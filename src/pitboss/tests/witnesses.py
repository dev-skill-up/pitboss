"""A state the shipped decider gives each worker task, and the one after its effects.

pitboss#526 (keyword: progress): a step a worker is told to do must change what the
step was decided from. For each ``Task`` of ``workerselect.TABLE`` a witness is a PR
(or the facts the settlers read) at which the shipped decider chooses the task, and
the same PR after the worker did the effects the table requires of it. The decider
is run on both, never a copy of its rules.
"""

import dataclasses
import functools
from typing import Callable, Mapping

from .. import (
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
from ..workerselect import Task
from . import blank, corpuseffects, derivedhand, headed, pullstates
from . import test_flow as sample
from .test_plan_digest_collapse import digest

Decide = Callable[[], steps.Move | None]
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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Witness:
    """The decider's step at a PR, and at the PR after its worker's effects.

    Attributes:
        before: the step at the PR.
        after: the step at the PR after the effects the table requires of the task.
    """

    before: Decide
    after: Decide


def _at(pr: flow.PullState, task: Task, body: str | None = None) -> Witness:
    done = corpuseffects.applied(pr, task, body)
    assert done is not None, task
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


def _restore() -> Witness:
    # the Plan edited after its approval, a ruling stands and a push followed it
    edited = BODY.replace("the plan", "the plan, edited")
    read = sample.graded(*sample.EXECUTION_REJECTED, 1)
    review = dataclasses.replace(read, plan_digest=digest(BODY))
    pushed = dataclasses.replace(sample.GREEN, started_at="2026-10-30T00:00:09Z")
    pr = sample.state(review, comments=[sample.ruling(2)], checks=[pushed], body=edited)
    return _at(pr, Task.RESTORE_PLAN, BODY)


def _execution() -> flow.PullState:
    first = sample.graded(*sample.EXECUTION_REJECTED, 1, sha=sample.OLDER)
    return sample.state(
        first, sample.graded(None, CHANGES, 3), comments=[sample.ruling(2)]
    )


def _stale() -> Witness:
    current = f"{BODY}\nHead: {HEAD}\n"
    older = f"{BODY}\nHead: {'b' * 40}\n"
    return _at(sample.state(body=older), Task.REFRESH_BODY, current)


def _quotes() -> Witness:
    unquoted = sample.state(PLAN_ONLY, body=f"Fixes #7\n\n{QUOTES_PLAN}\n{UNQUOTED}")
    return _at(unquoted, Task.ADD_CI_QUOTES, f"Fixes #7\n\n{QUOTES_PLAN}\n{QUOTED}")


def _handed_back() -> Witness:
    owed = pullstates.with_recorded(sample.state(), handed=derivedhand.held())
    return _at(owed, Task.HAND_BACK)


def _facts(step: steps.Move, ended: str = "") -> pullfacts.PullFacts:
    # the facts the settlers read of a PR at a step, whose one check failed at ``ended``
    run = dataclasses.replace(
        blank.CHECK_RUN, id=9, failed=True, finished=True, completed_at=ended
    )
    build = functools.partial(
        pullfacts.PullFacts,
        repo=config.make_repo("o", "r"),
        pull=sample.state().pull,
        checks=[run],
        review=None,
        standing=reviews.Standing.NONE,
        signals=headsignals.NONE,
        unreadable=straycomments.NONE,
    )
    return build(step=step, review_rounds=rounds.NONE, relock=False)


def _blocker(state: blockedstep.State, merged: str = "") -> blockedstep.Blocker:
    return blockedstep.Blocker(
        reference="o/r#1125", state=state, merged_at=merged, body=""
    )


RED = steps.worker(Task.FIX_CI)
OPEN = _blocker(blockedstep.State.OPEN)
MERGED = _blocker(blockedstep.State.MERGED, "2026-11-24T05:00:00Z")


def _shared() -> Witness:
    red = _facts(RED)
    holders = [pullref.reference(red), "o/r#99"]
    group = sharedstep.Shared(slug="o/r", check="c", line="boom", holders=holders)
    return Witness(
        before=lambda: sharedstep.stepped(red, [group]),
        # the PR names the ticket in a Blocked-by line: the shared red is not read
        after=lambda: blockedstep.verdict(red, [OPEN]),
    )


def _closed() -> Witness:
    shut = _blocker(blockedstep.State.CLOSED)
    red = _facts(RED)
    return Witness(
        before=lambda: blockedstep.verdict(red, [shut]),
        after=lambda: blockedstep.verdict(red, []),
    )


def _merged() -> Witness:
    # the red check ended before the blockers merged; a push ends a newer one
    older = _facts(RED, "2026-11-24T04:00:00Z")
    newer = _facts(RED, "2026-11-24T06:00:00Z")
    return Witness(
        before=lambda: blockedstep.verdict(older, [MERGED]),
        after=lambda: blockedstep.verdict(newer, [MERGED]),
    )


def _partial() -> Witness:
    bare = sample.state()
    kept = [each for each in bare.comments if not each.body.startswith("Plan check")]
    pr = dataclasses.replace(bare, comments=kept)
    done = corpuseffects.applied(pr, Task.FINISH_PARTIAL)
    assert done is not None

    def finish(at: flow.PullState) -> steps.Move | None:
        return finishstep.step_of(_facts(flow.next_step(at)))

    return Witness(before=lambda: finish(pr), after=lambda: finish(done))


BUILDERS: Mapping[Task, Callable[[], Witness]] = {
    Task.FIRST_ROUND: lambda: _at(
        sample.state(PLAN_REJECTION, body=""),
        Task.FIRST_ROUND,
        BODY,
    ),
    Task.FIX_CI: lambda: _at(sample.state(checks=(sample.RED,)), Task.FIX_CI),
    Task.REVISE_PLAN: lambda: _at(
        _rejecting(BODY), Task.REVISE_PLAN, BODY.replace("the plan", "the plan, edited")
    ),
    Task.RESTORE_PLAN: _restore,
    Task.RESOLVE_CONFLICT: lambda: _at(
        sample.state(mergeable_state="dirty"), Task.RESOLVE_CONFLICT
    ),
    Task.FIX_EXECUTION: lambda: _at(_execution(), Task.FIX_EXECUTION),
    Task.RULING_STEPS: lambda: _at(_ruled("do these steps"), Task.RULING_STEPS),
    Task.RULING_AS_GIVEN: lambda: _at(_ruled("split"), Task.RULING_AS_GIVEN),
    Task.RUN_PLAN: lambda: _at(
        sample.state(PLAN_ONLY, body=UNWRITTEN), Task.RUN_PLAN, BODY
    ),
    Task.ADD_CI_QUOTES: _quotes,
    Task.FIX_ROUND: lambda: _at(_findings(), Task.FIX_ROUND),
    Task.REFRESH_BODY: _stale,
    Task.SHARED_RED: _shared,
    Task.FIX_BLOCKED_BY: _closed,
    Task.AFTER_BLOCKER: _merged,
    Task.FINISH_PARTIAL: _partial,
    Task.HAND_BACK: _handed_back,
}
WITNESSES: Mapping[Task, Witness] = {task: build() for task, build in BUILDERS.items()}
