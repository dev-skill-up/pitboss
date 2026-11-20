"""A small model of a PR for the property tests (keyword: properties, pitboss#444).

A ``Model`` is what the events of the alphabet leave of a PR: the head, the CI,
the conflict, the pause, the Plan's version, and the reviews, rulings and Plan
checks with the time (the number of events so far) each came at. ``pull_state``
renders it as the ``PullState`` the flow reads, so every property runs the
shipped ``flow.next_step``.
"""

import dataclasses
from typing import Callable, Sequence

from .. import bodydigest, expansion, flow, plandigest, rulingwords, shapes, steps
from . import blank, checkcomment, pullstates, test_flow

Verdict = shapes.Verdict
Ruling = rulingwords.Ruling
Review = tuple[int, Verdict | None, Verdict | None, int, int]
Allowed = Callable[["Model"], bool]
FIRST = 3
DO_STEPS = "ruling do these steps"
STATES = {"green": (True, False), "red": (True, True), "running": (False, False)}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class History:
    """What was posted on the PR, each with the time it came at.

    Attributes:
        reviews: ``(when, plan, execution, head, plan version)`` of each review.
        rulings: ``(when, word)`` of each ruling.
        checks: ``(when, plan version, head)`` of each clean Plan check.
    """

    reviews: Sequence[Review] = ()
    rulings: Sequence[tuple[int, Ruling]] = ()
    checks: Sequence[tuple[int, int, int]] = ((2, 0, 0),)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Model:
    """What the events left of a PR.

    Attributes:
        head: the number of the head (a push makes the next).
        pushed: when the head was pushed.
        ci: ``green``, ``red`` or ``running`` on the head.
        conflict: whether the PR conflicts with main.
        paused: whether it carries the pause label.
        plan: the version of the Plan section.
        history: the reviews, rulings and Plan checks.
        since_pause: how many rulings were posted since the last pause.
        last: the name of the last event.
        clock: the number of events so far, as seconds.
    """

    head: int = 0
    pushed: int = 1
    ci: str = "green"
    conflict: bool = False
    paused: bool = False
    plan: int = 0
    history: History = History()
    since_pause: int = 0
    last: str = "start"
    clock: int = FIRST


def _times(model: Model) -> Sequence[int]:
    made = model.history
    return sorted(
        {model.pushed}
        | {each[0] for each in made.reviews}
        | {each[0] for each in made.rulings}
        | {each[0] for each in made.checks}
    )


def key(model: Model) -> Sequence[object]:
    """What makes a model distinct: the times only as their order.

    Two models that differ only in when events came, not in the order of them,
    or in the name of the last event but the ruling ``do these steps`` (which
    the properties read), read the same to the flow and to every property.

    Args:
        model: the PR.

    Returns:
        A value equal for models of the same order of events.
    """
    rank = {second: place for place, second in enumerate(_times(model))}
    made = model.history
    return [
        (model.head, model.ci, model.conflict, model.paused, model.plan),
        (model.since_pause, model.last == DO_STEPS, rank[model.pushed]),
        [(rank[a], b, c, d, e) for a, b, c, d, e in made.reviews],
        [(rank[a], b) for a, b in made.rulings],
        [(rank[a], b, c) for a, b, c in made.checks],
    ]


def stamp(second: int) -> str:
    """The time of the n-th event.

    Args:
        second: its number.

    Returns:
        An ISO 8601 time that orders as the numbers do.
    """
    return f"2026-10-30T00:00:{second:02d}Z"


def body_of(plan: int, head: int = 0) -> str:
    """The PR body with a version of the Plan, as it reads at a head.

    The Plan's CI pointer names the run of the head, so the body of another head
    differs in its run and job ids only (keyword: plan-digest-urls).

    Args:
        plan: the version.
        head: the head's number.

    Returns:
        The body.
    """
    url = f"https://github.com/o/r/actions/runs/{head + 100}/job/{head + 200}"
    return test_flow.BODY.replace("the plan", f"the plan v{plan} {url}")


def sha_of(head: int) -> str:
    """The sha of a head.

    Args:
        head: its number.

    Returns:
        Forty hex digits.
    """
    return f"{head + 1:040x}"


def _plan_check(plan: int, head: int, second: int) -> shapes.Comment:
    return dataclasses.replace(
        blank.COMMENT,
        body=checkcomment.clean_text(body_of(plan, head)),
        author_association="MEMBER",
        created_at=stamp(second),
        url=f"https://example.org/check/{second}",
    )


def _ruling(second: int, word: Ruling) -> shapes.Comment:
    return dataclasses.replace(
        blank.COMMENT,
        body=f"Opus ruling\nRuling: {word.value}\n",
        author_association="MEMBER",
        created_at=stamp(second),
        url=f"https://example.org/ruling/{second}",
    )


def _graded(each: Review) -> shapes.Graded:
    second, plan, execution, head, version = each
    body = body_of(version, head)
    return dataclasses.replace(
        blank.GRADED,
        sha=sha_of(head),
        when=stamp(second),
        plan=plan,
        execution=execution,
        body=bodydigest.digest(body),
        plan_digest=expansion.section_digest(plandigest.section(body)),
    )


def _check_runs(model: Model) -> Sequence[shapes.CheckRun]:
    finished, failed = STATES[model.ci]
    return [
        dataclasses.replace(
            blank.CHECK_RUN,
            id=1,
            name="build",
            finished=finished,
            failed=failed,
            started_at=stamp(model.pushed),
        )
    ]


def pull_state(model: Model) -> flow.PullState:
    """The state the flow reads of a model.

    Args:
        model: the PR.

    Returns:
        The state: a ready PR with a Plan and an Execution in its body.
    """
    head = {"sha": sha_of(model.head), "ref": "work"}
    dirty = "dirty" if model.conflict else "clean"
    pull = test_flow.pull_of(
        body=body_of(model.plan, model.head), head=head, mergeable_state=dirty
    )
    made = model.history
    comments = [_plan_check(plan, at, second) for second, plan, at in made.checks]
    comments += [_ruling(second, word) for second, word in made.rulings]
    return dataclasses.replace(
        pullstates.bare(pull),
        labels={steps.PAUSED_LABEL} if model.paused else set(),
        checks=_check_runs(model),
        graded=[_graded(each) for each in made.reviews],
        comments=comments,
    )


_STEPS: dict[str, steps.Move] = {}


def _step_of_key(token: str, model: Model) -> steps.Move:
    # models of one key read the same to the flow (see ``key``)
    if token not in _STEPS:
        _STEPS[token] = flow.next_step(pull_state(model))
    return _STEPS[token]


def step_of(model: Model) -> steps.Move:
    """The step the flow gives a model.

    Args:
        model: the PR.

    Returns:
        The step.
    """
    return _step_of_key(repr(key(model)), model)


def ci_waits(at: Model, step: steps.Move) -> bool:
    """Whether nobody acts on a PR until its CI finishes.

    A model PR is no draft, so no actor takes it only while it is paused or its
    CI has not finished (an idle step carries no reason: plan 6.2).

    Args:
        at: the PR.
        step: the PR's step.

    Returns:
        True for the CI's wait.
    """
    return isinstance(step, steps.Idle) and not at.paused
