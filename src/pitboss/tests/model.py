"""A small model of a PR for the property tests (keyword: properties, pitboss#444).

A ``Model`` is what the events of the alphabet leave of a PR: the head, the CI,
the conflict, the pause, the Plan's version, and the reviews, rulings and Plan
checks with the time (the number of events so far) each came at. ``pull_state``
renders it as the ``PullState`` the flow reads, so every property runs the
shipped ``flow.next_step``.
"""

import dataclasses
from typing import Callable, Mapping, Sequence

from .. import bodydigest, expansion, flow, plandigest, rulingwords, shapes, steps
from . import checkcomment, test_flow

Verdict = shapes.Verdict
Ruling = rulingwords.Ruling
Allowed = Callable[["Model"], bool]
FIRST = 3


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
        reviews: ``(when, plan, execution, head, plan version)`` of each review.
        rulings: ``(when, word)`` of each ruling.
        checks: ``(when, plan version)`` of each clean Plan check.
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
    reviews: Sequence[tuple[int, Verdict | None, Verdict | None, int, int]] = ()
    rulings: Sequence[tuple[int, Ruling]] = ()
    checks: Sequence[tuple[int, int]] = ((2, 0),)
    since_pause: int = 0
    last: str = "start"
    clock: int = FIRST


def key(model: Model) -> tuple[object, ...]:
    """What makes a model distinct: the times only as their order.

    Two models that differ only in when events came, not in the order of them,
    or in the name of the last event but the ruling ``do these steps`` (which
    the properties read), read the same to the flow and to every property.

    Args:
        model: the PR.

    Returns:
        A value equal for models of the same order of events.
    """
    times = sorted(
        {model.pushed}
        | {each[0] for each in model.reviews}
        | {each[0] for each in model.rulings}
        | {each[0] for each in model.checks}
    )
    rank = {second: place for place, second in enumerate(times)}
    return (
        model.head,
        model.ci,
        model.conflict,
        model.paused,
        model.plan,
        model.since_pause,
        model.last == "ruling do these steps",
        rank[model.pushed],
        tuple((rank[a], b, c, d, e) for a, b, c, d, e in model.reviews),
        tuple((rank[a], b) for a, b in model.rulings),
        tuple((rank[a], b) for a, b in model.checks),
    )


def stamp(second: int) -> str:
    """The time of the n-th event.

    Args:
        second: its number.

    Returns:
        An ISO 8601 time that orders as the numbers do.
    """
    return f"2026-10-30T00:00:{second:02d}Z"


def body_of(plan: int) -> str:
    """The PR body with a version of the Plan.

    Args:
        plan: the version.

    Returns:
        The body.
    """
    return test_flow.BODY.replace("the plan", f"the plan v{plan}")


def sha_of(head: int) -> str:
    """The sha of a head.

    Args:
        head: its number.

    Returns:
        Forty hex digits.
    """
    return f"{head + 1:040x}"


def _check(plan: int, second: int) -> shapes.Comment:
    return shapes.Comment(
        body=checkcomment.clean_text(body_of(plan)),
        author_association="MEMBER",
        created_at=stamp(second),
        url=f"https://example.org/check/{second}",
    )


def _ruling(second: int, word: Ruling) -> shapes.Comment:
    return shapes.Comment(
        body=f"Opus ruling\nRuling: {word.value}\n",
        author_association="MEMBER",
        created_at=stamp(second),
        url=f"https://example.org/ruling/{second}",
    )


def _graded(each: tuple[int, Verdict | None, Verdict | None, int, int]) -> shapes.Graded:
    second, plan, execution, head, version = each
    body = body_of(version)
    return shapes.Graded(
        sha=sha_of(head),
        when=stamp(second),
        plan=plan,
        execution=execution,
        body=bodydigest.digest(body),
        plan_digest=expansion.section_digest(plandigest.section(body)),
    )


def _checks(model: Model) -> Sequence[shapes.CheckRun]:
    state = {"green": (True, False), "red": (True, True), "running": (False, False)}
    finished, failed = state[model.ci]
    return [
        shapes.CheckRun(
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
    body = body_of(model.plan)
    head = {"sha": sha_of(model.head), "ref": "work"}
    dirty = "dirty" if model.conflict else "clean"
    pull = test_flow.pull_of(body=body, head=head, mergeable_state=dirty)
    comments = [_check(plan, second) for second, plan in model.checks]
    comments += [_ruling(second, word) for second, word in model.rulings]
    return flow.PullState(
        pull=pull,
        labels=frozenset({steps.PAUSED_LABEL}) if model.paused else frozenset(),
        checks=_checks(model),
        graded=[_graded(each) for each in model.reviews],
        comments=comments,
        trusted=frozenset({"MEMBER"}),
    )


def step_of(model: Model) -> steps.Next:
    """The step the flow gives a model.

    Args:
        model: the PR.

    Returns:
        The step.
    """
    return flow.next_step(pull_state(model))


def _then(model: Model, name: str, **changes: object) -> Model:
    return dataclasses.replace(model, last=name, clock=model.clock + 1, **changes)


def _review(
    model: Model, name: str, plan: Verdict | None, execution: Verdict | None
) -> Model:
    each = (model.clock, plan, execution, model.head, model.plan)
    return _then(model, name, reviews=[*model.reviews, each])


def _push(model: Model, name: str, checked: bool) -> Model:
    made = [(model.clock, model.plan)] if checked else []
    return _then(
        model,
        name,
        head=model.head + 1,
        pushed=model.clock,
        ci="running",
        checks=[*model.checks, *made],
    )


def allowed_once(model: Model) -> bool:
    """Whether ``ruling post`` accepts a ruling: none since the last pause.

    Args:
        model: the PR.

    Returns:
        True when no ruling was posted since the PR was last paused.
    """
    return model.since_pause == 0


def ruled(model: Model, word: Ruling, allowed: Allowed) -> Model | None:
    """A ruling posted, when the rule lets it.

    Args:
        model: the PR.
        word: what it rules.
        allowed: the rule for a ruling (``allowed_once``).

    Returns:
        The model with the ruling, None when the rule refuses it.
    """
    if not allowed(model):
        return None
    made = [*model.rulings, (model.clock, word)]
    return _then(
        model,
        "ruling " + word.value,
        rulings=made,
        since_pause=model.since_pause + 1,
    )


def paused(model: Model) -> Model:
    """The PR labelled for the owner.

    Args:
        model: the PR.

    Returns:
        The model with the label, and the count of rulings since the pause 0.

    """
    return _then(model, "label", paused=True, since_pause=0)


def _plain(model: Model) -> Mapping[str, Callable[[Model], Model]]:
    return {
        "plan review": lambda m: _review(m, "plan review", Verdict.APPROVED, None),
        "execution review rejects": lambda m: _review(
            m, "execution review rejects", Verdict.APPROVED, Verdict.CHANGES_NEEDED
        ),
        "review approves": lambda m: _review(
            m, "review approves", Verdict.APPROVED, Verdict.APPROVED
        ),
        "plan rejected": lambda m: _review(
            m, "plan rejected", Verdict.CHANGES_NEEDED, None
        ),
        "plan check at a new head": lambda m: _push(m, "plan check", True),
        "push": lambda m: _push(m, "push", False),
        "merge of main": lambda m: dataclasses.replace(
            _push(m, "merge of main", False), conflict=False
        ),
        "ci green": lambda m: _then(m, "ci green", ci="green"),
        "ci red": lambda m: _then(m, "ci red", ci="red"),
        "label": paused,
        "conflict": lambda m: _then(m, "conflict", conflict=True),
    }


RULINGS = (Ruling.DO_THESE_STEPS, Ruling.REVISE_THE_PLAN, Ruling.ESCALATE)


def moves(model: Model, allowed: Allowed = allowed_once) -> Sequence[Model]:
    """Every model one event of the alphabet leads to.

    Args:
        model: the PR.
        allowed: the rule for a ruling.

    Returns:
        The models; an event the rules refuse (a second ruling) leads nowhere.
    """
    found = [each(model) for each in _plain(model).values()]
    found += [ruled(model, word, allowed) for word in RULINGS]
    return [each for each in found if each is not None]


def simulated(model: Model, step: steps.Next, allowed: Allowed) -> Model | None:
    """The model after the step is done as it says.

    Args:
        model: the PR.
        step: the step printed for it.
        allowed: the rule for a ruling.

    Returns:
        The model, None for a step that waits for the owner or ends the PR.
    """
    named = step.step
    done = {
        steps.Step.WAIT_FOR_CI: lambda: _then(model, "ci green", ci="green"),
        steps.Step.OPUS_RULING: lambda: ruled(model, Ruling.DO_THESE_STEPS, allowed),
        steps.Step.PAUSE_FOR_OWNER: lambda: paused(model),
        steps.Step.PLAN_CHECK: lambda: _then(
            model, "plan check", checks=[*model.checks, (model.clock, model.plan)]
        ),
        steps.Step.SEND_BACK_PLAN_CHECK: lambda: _push(model, "send back", True),
        steps.Step.REGULAR_REVIEW: lambda: _reviewed(model, step),
        steps.Step.WORKER: lambda: _worked(model, step),
    }
    return done[named]() if named in done else None


def _reviewed(model: Model, step: steps.Next) -> Model:
    alone = step.stage is steps.Stage.PLAN_ONLY
    return _review(model, "review", Verdict.APPROVED, None if alone else Verdict.APPROVED)


def _worked(model: Model, step: steps.Next) -> Model:
    task = step.task
    if task is steps.Task.RESOLVE_CONFLICT:
        return dataclasses.replace(_push(model, "worker", False), conflict=False, ci="green")
    if task is steps.Task.FIX_CI:
        return dataclasses.replace(_push(model, "worker", False), ci="green")
    pushed = _push(model, "worker", True)
    revised = dataclasses.replace(pushed, ci="green")
    if task is steps.Task.REVISE_PLAN:
        return dataclasses.replace(
            revised, plan=model.plan + 1, checks=[*model.checks, (model.clock, model.plan + 1)]
        )
    return revised
